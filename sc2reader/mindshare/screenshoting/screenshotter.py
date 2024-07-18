import time
import pandas as pd
import pyautogui
from datetime import datetime, timedelta
from sc2reader.mindshare.fileHandler import FileHandler
import sc2reader

import tkinter as tk
import threading
import ctypes
import cv2
import numpy as np
import mss
import argparse


class Screenshotter():

    INTERVAL_MARGIN = 2
    SCREENSHOT_INTERVAL = 2
    COUNTDOWN_SIZE = "200x100"
    COUNTDOWN_POSITION = "+200+200"

    MOVE_MOUSE_INTERVAL = 30

    #TODO the folders should be provided to all entities in the process by some helper class
    def __init__(self, replay, playerName) -> None:

        self.playerName = playerName

        self.fh = FileHandler(replay)
        
        self.processedIntervals = list()
        self.endTimes = list()

        self.fps = 30
        self.duration = None
        self.readIntervals()

    def readIntervals(self):    
        """Read time intervals from a CSV file and return a list of tuples (start, end, id)."""
        try:
            df = pd.read_csv(self.fh.intervalsFile)
            self.intervals = [(row['start'], row['end'], row['id']) for _, row in df.iterrows()]

            self.duration = self.totalSeconds(datetime.strptime(self.intervals[-1][1], "%H:%M:%S").time()) + 5
            print(self.duration)
        except FileNotFoundError:
            print(f"File not found: {self.fh.intervalsFile}")
            raise
    
    def totalSeconds(self, time):
        return int(time.hour * 3600 + time.minute * 60 + time.second)
    
    def countdown(self):
            """Display a countdown before starting the timer."""
            root = tk.Tk()
            root.overrideredirect(True)  # Remove window decorations
            root.geometry(self.COUNTDOWN_SIZE + self.COUNTDOWN_POSITION)  # Position the window
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

    def preventSleep(self):
        start_time = time.time()
        while time.time() - start_time < (self.duration - 30):
            current_x, current_y = pyautogui.position()
            pyautogui.moveTo(current_x + 10, current_y)  # Move the mouse slightly
            pyautogui.moveTo(current_x, current_y)  # Move it back to the original position
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)  # Prevent the system from sleeping
            time.sleep(self.MOVE_MOUSE_INTERVAL)  # Wait for the specified period

    def extractFrames(self):
        # Open the video file
        cap = cv2.VideoCapture("{}/{}".format(self.fh.gameFolder, self.fh.getPlayerVideoFileName(self.playerName)))

        for start, end, battle_id in self.intervals:
            # Convert times to frame numbers
            start_time = datetime.strptime(start, "%H:%M:%S")
            end_time = datetime.strptime(end, "%H:%M:%S")

            if start_time == end_time:
                end_time += timedelta(seconds=2)

            start_frame = self.totalSeconds(start_time) * self.fps
            end_frame = self.totalSeconds(end_time) * self.fps

            # Set the current frame position to start
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

            for frame_num in range(start_frame, end_frame, int(2 * self.fps)):  # Capture every 2 seconds
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                ret, frame = cap.read()

                #TODO add screenshot creation to file handler
                if ret:
                    timestamp = str(timedelta(seconds=frame_num/self.fps))
                    output_file = "{}/{}_{}_at_{}.png".format(
                        self.fh.screenshotsFolder,
                        battle_id, 
                        self.playerName, 
                        timestamp.replace(":","-"))
                    
                    cv2.imwrite(output_file, frame)
                    print(f"Screenshots created: {battle_id} at {timestamp} to {output_file}")
                else:
                    print(f"Failed to capture frame at {timestamp}")

        # Release the video capture object
        cap.release()

    def startRecording(self):

        self.countdown()

        #start recording
        pyautogui.hotkey('winleft', 'shift', 'r')
        print("recording UI up at " + str(datetime.now()))
        time.sleep(1)

        #select record area as a whole screen
        pyautogui.moveTo(1, 1)
        pyautogui.mouseDown()
        pyautogui.moveTo(2558, 1598, 1)#2559, 1599
        pyautogui.mouseUp()
        print("recording area set at " + str(datetime.now()))
        time.sleep(1)

        #click start recording
        pyautogui.click(1154, 47)
        pyautogui.click(1154, 47)
        print("recording started at " + str(datetime.now()))

        time.sleep(3)
        pyautogui.click(51, 794)

        thread = threading.Thread(target=self.preventSleep)
        thread.start()

        #wait for the duration of the game
        time.sleep(self.duration)
        
        #stop recording
        pyautogui.click(1178, 46)
        pyautogui.click(1178, 46)
        print("recording ended at " + str(datetime.now()))
        time.sleep(1)

        #maximise sniping tool window with the recording
        pyautogui.hotkey('winleft', 'up')
        time.sleep(1)
        print("window maxed at " + str(datetime.now()))

        #click save video
        pyautogui.click(2379, 81)
        time.sleep(1)
        print("video save popup at " + str(datetime.now()))

        #confirm save
        pyautogui.write(self.fh.getPlayerVideoFileName(self.playerName))
        time.sleep(1)
        pyautogui.click(823, 131)
        time.sleep(1)
        pyautogui.write(self.fh.gameFolder)
        time.sleep(1)
        pyautogui.click(1012, 783)
        #pyautogui.click(1040, 801)
        print("video saved at " + str(datetime.now()))

        #close snipping tool window
        time.sleep(2)
        pyautogui.click(2529, 31)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Script to create capture game video for a player and create screenshots from that')
    parser.add_argument('--replay', type=str, help='Name of the replay file')
    parser.add_argument('--player', type=str, help='Name of the player in the video')
    
    args = parser.parse_args()
    
    process = Screenshotter(sc2reader.load_replay(FileHandler.REPLAYS_FOLDER + "/" + "Skippy_Oceanborn LE (24).SC2Replay", debug=True, load_map=True), "SkippyJo")
    #process.startRecording()

    #file needs to be fully saved before screenshotting give it some time
    #time.sleep(5)
    process.extractFrames()
