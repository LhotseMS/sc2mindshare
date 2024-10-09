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

from PIL import Image


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

class Screenshotter():

    INTERVAL_MARGIN = 2
    SCREENSHOT_INTERVAL = 2
    COUNTDOWN_SIZE = "200x100"
    COUNTDOWN_POSITION = "+200+200"

    MOVE_MOUSE_INTERVAL = 10

    #TODO the folders should be provided to all entities in the process by some helper class
    def __init__(self, replay, p1n, p2n) -> None:

        self.player1Name = p1n
        self.player2Name = p2n

        self.fh = FileHandler(replay)
        
        self.processedIntervals = list()
        self.endTimes = list()

        self.fps = 30
        self.duration = None
        self.readIntervals()


    #TODO read should go to FH
    def readIntervals(self):    
        """Read time intervals from a CSV file and return a list of tuples (start, end, id)."""
        try:
            df = pd.read_csv(self.fh.intervalsFile)
            self.intervals = [(row['start'], row['end'], row['id']) for _, row in df.iterrows()]

            self.duration = self.totalSeconds(datetime.strptime(self.intervals[-1][1], "%H:%M:%S").time()) + 5
            print("The recording will take {}s".format(2 * int(self.duration)))
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

    def preventSleep(self, stopEvent):
        start_time = time.time()
        while time.time() - start_time < (self.duration - 30) and not stopEvent.is_set():
            current_x, current_y = pyautogui.position()
            pyautogui.moveTo(current_x + 10, current_y + 10)  # Move the mouse slightly
            time.sleep(1)
            pyautogui.moveTo(current_x, current_y)  # Move it back to the original position
            #ctypes.windll.kernel32.SetThreadExecutionState(0x80000002)  # Prevent the system from sleeping
            
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)

            time.sleep(self.MOVE_MOUSE_INTERVAL)  # Wait for the specified period

    def extractFrames(self):

        logo = Image.open("C:/MS SC/mindshareLogo.png")
        logo_width, logo_height = logo.size
        logo = logo.resize((round(logo_width * 0.2), round(logo_height * 0.2)))
        logo_width, logo_height = logo.size

        arrow = Image.open("C:/MS SC/orangeArrow.png")
        arrow_width, arrow_height = arrow.size
        arrow = arrow.resize((round(arrow_width * 0.16), round(arrow_height * 0.16)))
        arrow_width, arrow_height = arrow.size

        for playerName, arrowYOffset in ((self.player1Name, 80), (self.player2Name, 180)):
            # Open the video file

            videoFileName = self.fh.getPlayerVideoFileName(playerName)
            cap = cv2.VideoCapture("{}/{}".format(self.fh.gameFolder, videoFileName))
            
            print(f"Opening video {videoFileName} for {playerName}")

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

                    if ret:
                        # Convert the frame to a PIL image
                        frame_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

                        # Get the dimensions of the frame and the logo and Calculate position to place the logo (top right corner)
                        frame_width, frame_height = frame_pil.size
                        frame_pil.paste(logo, 
                                        (frame_width - logo_width - 30, 20), 
                                        logo.convert("RGBA"))
                        
                        frame_pil.paste(arrow, 
                                        (370, frame_height - arrowYOffset), 
                                        arrow.convert("RGBA"))

                        # Convert PIL Image to OpenCV format
                        frame_cv2 = cv2.cvtColor(np.array(frame_pil), cv2.COLOR_RGB2BGR)

                        # Resize the image using OpenCV
                        coef = 0.7
                        resized_frame_cv2 = cv2.resize(frame_cv2, 
                                                       (round(frame_width * coef), round(frame_height * coef)), 
                                                       interpolation=cv2.INTER_AREA)

                        # Create the output file
                        timestamp = str(timedelta(seconds=frame_num / self.fps))
                        output_file = "{}/{}_{}_at_{}.png".format(
                            self.fh.imagesFolder,
                            timestamp.replace(":", "-"),
                            battle_id,
                            playerName)

                        # Save the frame with the logo
                        cv2.imwrite(output_file, resized_frame_cv2)
                        print(f"Screenshots created: {battle_id} at {timestamp} to {output_file}")
                    else:
                        print(f"Failed to capture frame at {timestamp}")

            # Release the video capture object
            cap.release()

    def startRecording(self):

        #stopEvent = threading.Event()
        #thread = threading.Thread(target=self.preventSleep, args=(stopEvent,))
        #thread.start()

        print("Select player 1 " + str(datetime.now()))
        pyautogui.press("1")
        self.recordOnePlayer(self.player1Name)

        pyautogui.click(2529, 31)
        pyautogui.click(2529, 31)
        time.sleep(1)

        #sometime game ends and there should be a click on return to game button        

        print("Restart replay " + str(datetime.now()))
        pyautogui.hotkey('ctrl', 'e')
        pyautogui.hotkey('ctrl', 'e')
        time.sleep(5)

        print("Select player 2 " + str(datetime.now()))
        pyautogui.press("2")

        self.recordOnePlayer(self.player2Name)

        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        #stopEvent.set()
        #thread.join()

    def recordOnePlayer(self, playerName):

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
        #click on play in classic replay gui
        #pyautogui.click(51, 794)
        pyautogui.click(2538, 10)
        pyautogui.click(2538, 10)
        pyautogui.press("p")

        #wait for the duration of the game, last battle interval
        time.sleep(self.duration)
        self.countdown()
        
        # P NEEDS to pauze the game so that the next round of recording starts from pause
        pyautogui.press("p")

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
        time.sleep(3)
        print("video save popup at " + str(datetime.now()))

        #confirm save
        pyautogui.write(self.fh.getPlayerVideoFileName(playerName))
        time.sleep(3)
        pyautogui.click(823, 131)
        time.sleep(3)
        pyautogui.write(self.fh.gameFolder)
        time.sleep(3)
        pyautogui.click(1040, 801)
        pyautogui.press('enter')
        
        #pyautogui.click(1012, 783)
        print("video saved at " + str(datetime.now()))

        #close snipping tool window
        time.sleep(2)
        pyautogui.click(2529, 31)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Script to create capture game video for a player and create screenshots from that')
    parser.add_argument('--replay', type=str, help='Name of the replay file')
    parser.add_argument('--p1', type=str, help='Name of the player in the video')
    parser.add_argument('--p2', type=str, help='Name of the other player in the video')
    parser.add_argument('--mode', type=str, help='Name of the other player in the video')
    
    args = parser.parse_args()
    
    process = Screenshotter(sc2reader.load_replay(FileHandler.REPLAYS_FOLDER + "/" + args.replay, debug=True, load_map=True), args.p1, args.p2)

    if args.mode == "rs" or args.mode == "r":
        process.startRecording()

    if args.mode == "rs" or args.mode == "s":
        process.extractFrames()
    
    time.sleep(5)
    
    
    #file needs to be fully saved before screenshotting give it some time
    
