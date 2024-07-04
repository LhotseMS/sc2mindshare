import time
import pandas as pd
import pyautogui
import os
from datetime import datetime, timedelta
import tkinter as tk
import threading
import cv2
import numpy as np
import mss


# 1. Export battle times to game_battleID_intervals.csv
# 2. Read intervals make screenshots battle_player_second
# 3. Run export again reading the screenshots from a folder, 
# 4. assigninng screenshots names to battle images
# 5. upload images to mindshare picture

class Screenshotter():

    PLAYER_NAME = "SkippyJo"
    INTERVALS_FILE = ".intervals_Oceanborn LE__Player 1 - SkippyJo (Zerg)_vs_Player 2 - Fluffy (Protoss).csv"
    VIDEO_FILE = "Oceanborn LE__Player 1 - SkippyJo (Zerg)_vs_Player 2 - Fluffy (Protoss).avi"

    INTERVAL_MARGIN = 2
    SCREENSHOT_INTERVAL = 2
    COUNTDOWN_SIZE = "200x100"
    COUNTDOWN_POSITION = "+200+200"

    def __init__(self) -> None:

        script_dir = os.path.dirname(os.path.abspath(__file__))
        parent_of_parent_dir = os.path.abspath(os.path.join(script_dir, "../../"))

        self.processedIntervals = list()
        self.endTimes = list()

        self.INTERVALS_FILE_PATH = parent_of_parent_dir + "/output/intervals/" + self.INTERVALS_FILE
        self.IMAGE_OUTPUT_FOLDER = parent_of_parent_dir + "/output/screenshots/" 
        self.VIDEO_OUTPUT_FOLDER = parent_of_parent_dir + "/output/videos/" 

        self.duration = None
        self.readIntervals()

    def readIntervals(self):    
        """Read time intervals from a CSV file and return a list of tuples (start, end, id)."""
        try:
            df = pd.read_csv(self.INTERVALS_FILE_PATH)
            self.intervals = [(row['start'], row['end'], row['id']) for _, row in df.iterrows()]

            self.duration = self.totalSeconds(datetime.strptime(self.intervals[-1][1], "%H:%M:%S").time())
            print(self.duration)
        except FileNotFoundError:
            print(f"File not found: {self.INTERVALS_FILE_PATH}")
            raise

    def recordVideo(self, fps=12): # 14.3

        print("Recording started")

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screen_width = monitor["width"]
            screen_height = monitor["height"]

            # Define the codec and create VideoWriter object
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            out = cv2.VideoWriter(self.VIDEO_OUTPUT_FOLDER + self.VIDEO_FILE, fourcc, fps, (screen_width, screen_height))

            # Start the prevent_lock_screen function in a separate thread
            threading.Thread(target=self.prevent_lock_screen, daemon=True).start()
            # Record video for the specified duration
            for _ in range(int(fps * self.duration)):
                img = sct.grab(monitor)
                frame = np.array(img)

                # Convert from BGRA to BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                out.write(frame)

            # Release everything when the job is finished
            out.release()
    
    def prevent_lock_screen(self, interval=20):
        """Move the mouse slightly every 'interval' seconds to prevent screen lock."""
        while True:
            pyautogui.moveRel(10, 0)  # Move the mouse by 1 pixel right
            pyautogui.moveRel(-10, 0)  # Move the mouse back to the left
            time.sleep(interval)


    def totalSeconds(self, time):
        return int(time.hour * 3600 + time.minute * 60 + time.second)

    def extractFrames(self, fps=30):
        # Open the video file
        cap = cv2.VideoCapture(self.VIDEO_OUTPUT_FOLDER + "Recording 2024-07-04 151225.mp4")

        # Ensure the output folder exists
        if not os.path.exists(self.IMAGE_OUTPUT_FOLDER):
            os.makedirs(self.IMAGE_OUTPUT_FOLDER)

        for start, end, interval_id in self.intervals:
            # Convert times to frame numbers
            start_time = datetime.strptime(start, "%H:%M:%S")
            end_time = datetime.strptime(end, "%H:%M:%S")
            start_frame = self.totalSeconds(start_time) * fps
            end_frame = self.totalSeconds(end_time) * fps

            # Set the current frame position to start
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            for frame_num in range(start_frame, end_frame, int(2 * fps)):  # Capture every 2 seconds
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()

                if ret:
                    # Save the frame as an image file
                    # timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_file = os.path.join(self.IMAGE_OUTPUT_FOLDER, f"{interval_id}_frame_at_{frame_num}.png")
                    cv2.imwrite(output_file, frame)
                    print(f"Saved frame from {interval_id} at frame {frame_num} to {output_file}")
                else:
                    print(f"Failed to capture frame at frame {frame_num}")

        # Release the video capture object
        cap.release()

    def countdown(self):
        """Display a countdown before starting the timer."""
        root = tk.Tk()
        root.overrideredirect(True)  # Remove window decorations
        root.geometry(self.COUNTDOWN_SIZE+self.COUNTDOWN_POSITION)  # Position the window
        root.attributes('-topmost', True)

        label = tk.Label(root, font=('Helvetica', 48))
        label.pack(expand=True)

        def update_label(count):
            if count >= 0:
                label.config(text=str(count) if count > 0 else "GO")
                root.after(1000, update_label, count - 1)
            else:
                root.destroy()

        update_label(3)  # Start countdown from 3
        root.mainloop()

def main():

    process = Screenshotter()
    
    #process.countdown()

    #process.recordVideo()
    process.extractFrames()

    pass

if __name__ == "__main__":

    main()
