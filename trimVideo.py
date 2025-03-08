import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QFileDialog, QLabel, QSlider, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
import cv2
from moviepy.video.io.VideoFileClip import VideoFileClip
import os
import subprocess  # Add this import at the top
from dataclasses import dataclass
from typing import List

@dataclass
class Segment:
    start: int
    end: int
    
    def duration(self):
        return self.end - self.start

class VideoTrimmer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Trimmer")
        self.setGeometry(100, 100, 800, 600)

        # Initialize variables
        self.video_path = None
        self.video_duration = 0
        self.start_time = 0
        self.end_time = 0
        self.current_time = 0
        self.segments: List[Segment] = []

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Create video widget
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)
        
        # Create media player
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)
        self.media_player.errorOccurred.connect(self.handle_error)
        
        # Add position tracking
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)

        # Add progress slider
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.sliderMoved.connect(self.set_position)
        layout.addWidget(self.progress_slider)

        # Create controls
        controls_layout = QHBoxLayout()
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.play_pause)
        controls_layout.addWidget(self.play_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_video)
        controls_layout.addWidget(self.stop_button)

        # Add speed control button
        self.speed_button = QPushButton("1.0x")
        self.speed_button.clicked.connect(self.toggle_speed)
        self.current_speed_idx = 0
        self.speeds = [1.0, 1.5, 2.0, 0.5]
        controls_layout.addWidget(self.speed_button)

        self.select_button = QPushButton("Select Video")
        self.select_button.clicked.connect(self.select_video)
        controls_layout.addWidget(self.select_button)

        self.add_segment_button = QPushButton("Add Segment")
        self.add_segment_button.clicked.connect(self.add_current_segment)
        controls_layout.addWidget(self.add_segment_button)
        
        self.clear_segments_button = QPushButton("Clear Segments")
        self.clear_segments_button.clicked.connect(self.clear_segments)
        controls_layout.addWidget(self.clear_segments_button)

        layout.addLayout(controls_layout)

        # Create sliders
        slider_layout = QVBoxLayout()
        
        # Start time slider
        start_layout = QHBoxLayout()
        self.start_label = QLabel("Start Time: 0:00")
        self.start_slider = QSlider(Qt.Orientation.Horizontal)
        self.start_slider.valueChanged.connect(self.update_start_time)
        start_layout.addWidget(self.start_label)
        start_layout.addWidget(self.start_slider)
        slider_layout.addLayout(start_layout)

        # End time slider
        end_layout = QHBoxLayout()
        self.end_label = QLabel("End Time: 0:00")
        self.end_slider = QSlider(Qt.Orientation.Horizontal)
        self.end_slider.valueChanged.connect(self.update_end_time)
        end_layout.addWidget(self.end_label)
        end_layout.addWidget(self.end_slider)
        slider_layout.addLayout(end_layout)

        layout.addLayout(slider_layout)

        # Add segments list display
        self.segments_list = QLabel("Selected Segments:\nNone")
        layout.addWidget(self.segments_list)

        # Save button
        self.save_button = QPushButton("Save Trimmed Video")
        self.save_button.clicked.connect(self.save_video)
        self.save_button.setEnabled(False)
        layout.addWidget(self.save_button)

        # Duration label
        self.duration_label = QLabel("Duration: 0:00")
        layout.addWidget(self.duration_label)

    def select_video(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Video File", "",
                                                 "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file_name:
            self.video_path = file_name
            self.load_video()

    def load_video(self):
        # Get video duration using OpenCV
        cap = cv2.VideoCapture(self.video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.video_duration = int(total_frames / fps)
        cap.release()

        # Set up sliders
        self.start_slider.setRange(0, self.video_duration)
        self.end_slider.setRange(0, self.video_duration)
        self.end_slider.setValue(self.video_duration)
        self.end_time = self.video_duration

        # Update labels
        self.update_duration_label()
        
        # Enable save button
        self.save_button.setEnabled(True)

        # Load video into player - Update this part
        self.media_player.setSource(QUrl.fromLocalFile(self.video_path))

    def update_start_time(self):
        self.start_time = self.start_slider.value()
        # Ensure start time doesn't go past end time
        if self.start_time >= self.end_time:
            self.start_time = self.end_time - 1
            self.start_slider.setValue(self.start_time)
            return  # Return early to prevent unnecessary updates
        
        self.start_label.setText(f"Start Time: {self.format_time(self.start_time)}")
        self.update_duration_label()
        
        # Update video position when slider moves
        self.media_player.setPosition(self.start_time * 1000)
        
        # If video is playing, pause it while sliding
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_button.setText("Play")

    def update_end_time(self):
        self.end_time = self.end_slider.value()
        if self.end_time <= self.start_time:
            self.end_time = self.start_time + 1
            self.end_slider.setValue(self.end_time)
        self.end_label.setText(f"End Time: {self.format_time(self.end_time)}")
        self.update_duration_label()
        
        # Update video position when slider moves
        self.media_player.setPosition(self.end_time * 1000)
        
        # If video is playing, pause it while sliding
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_button.setText("Play")

    def update_duration_label(self):
        duration = self.end_time - self.start_time
        self.duration_label.setText(f"Duration: {self.format_time(duration)}")

    def format_time(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"

    def play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.play_button.setText("Play")
        else:
            # Start from start_time when playing
            current_pos = self.media_player.position() // 1000
            if current_pos < self.start_time or current_pos >= self.end_time:
                self.media_player.setPosition(self.start_time * 1000)
            self.media_player.play()
            self.play_button.setText("Pause")

    def save_video(self):
        if not self.video_path or not self.segments:
            return

        # Generate default output filename
        file_dir = os.path.dirname(self.video_path)
        file_name, file_extension = os.path.splitext(os.path.basename(self.video_path))
        default_name = f"{file_name}_combined{file_extension}"
        default_path = os.path.join(file_dir, default_name)

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Combined Video",
            default_path,
            "Video Files (*.mp4 *.avi *.mov *.mkv)"
        )
        
        if not output_path:
            return

        try:
            processing_label = QLabel("Processing video... Please wait.", self)
            processing_label.setStyleSheet("background-color: rgba(0,0,0,0.7); color: white; padding: 20px;")
            processing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            processing_label.setGeometry(self.width()//2 - 100, self.height()//2 - 25, 200, 50)
            processing_label.show()
            QApplication.processEvents()

            # Create temporary file for segment list
            with open('segments.txt', 'w') as f:
                for segment in self.segments:
                    duration = segment.end - segment.start
                    f.write(f"file '{self.video_path}'\n")
                    f.write(f"inpoint {segment.start}\n")
                    f.write(f"outpoint {segment.end}\n")

            # Use FFmpeg to concatenate segments
            command = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', 'segments.txt',
                '-c', 'copy',
                output_path
            ]
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            # Clean up temporary file
            os.remove('segments.txt')
            
            if result.returncode != 0:
                raise Exception(f"FFmpeg error: {result.stderr}")
            
            processing_label.hide()
            QMessageBox.information(self, "Success", "Video segments combined successfully!")
            
        except Exception as e:
            if 'processing_label' in locals():
                processing_label.hide()
            QMessageBox.critical(self, "Error", f"An error occurred while saving the video:\n{str(e)}")

    # Add this new method to handle media player errors
    def handle_error(self, error, error_string):
        print(f"Media Player Error: {error_string}")

    def position_changed(self, position):
        # Convert position from milliseconds to seconds
        position_secs = position // 1000
        
        # Update progress slider
        self.progress_slider.setValue(position)
        
        # If position is outside our trim range, move it
        if position_secs < self.start_time:
            self.media_player.setPosition(self.start_time * 1000)
        elif position_secs > self.end_time:
            self.media_player.pause()
            self.media_player.setPosition(self.start_time * 1000)
            self.play_button.setText("Play")

    def duration_changed(self, duration):
        self.progress_slider.setRange(0, duration)

    def set_position(self, position):
        self.media_player.setPosition(position)

    def stop_video(self):
        self.media_player.pause()
        self.media_player.setPosition(self.start_time * 1000)
        self.play_button.setText("Play")

    def toggle_speed(self):
        self.current_speed_idx = (self.current_speed_idx + 1) % len(self.speeds)
        new_speed = self.speeds[self.current_speed_idx]
        self.speed_button.setText(f"{new_speed}x")
        self.media_player.setPlaybackRate(new_speed)

    def add_current_segment(self):
        if self.start_time >= self.end_time:
            QMessageBox.warning(self, "Invalid Segment", "Start time must be before end time")
            return
            
        new_segment = Segment(self.start_time, self.end_time)
        self.segments.append(new_segment)
        self.update_segments_display()
        
    def clear_segments(self):
        self.segments.clear()
        self.update_segments_display()
        
    def update_segments_display(self):
        if not self.segments:
            self.segments_list.setText("Selected Segments:\nNone")
            return
            
        segments_text = "Selected Segments:\n"
        total_duration = 0
        for i, seg in enumerate(self.segments, 1):
            segments_text += f"{i}. {self.format_time(seg.start)} - {self.format_time(seg.end)} (Duration: {self.format_time(seg.duration())})\n"
            total_duration += seg.duration()
        segments_text += f"\nTotal Duration: {self.format_time(total_duration)}"
        self.segments_list.setText(segments_text)

def main():
    app = QApplication(sys.argv)
    window = VideoTrimmer()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
