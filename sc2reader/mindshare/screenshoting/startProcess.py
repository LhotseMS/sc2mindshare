import time
import pandas as pd
import pyautogui
import tkinter as tk
import os
import sys
from datetime import datetime, timedelta


# 1. Export battle times to game_battleID_intervals.csv
# 2. Read intervals make screenshots battle_player_second
# 3. Run export again reading the screenshots from a folder, 
# 4. assigninng screenshots names to battle images
# 5. upload images to mindshare picture
#

class ScreeningProcess():

    PLAYER_NAME = "SkippyJo"
    INTERVALS_FILE = ".intervals_Oceanborn LE__Player 1 - SkippyJo (Zerg)_vs_Player 2 - Fluffy (Protoss).csv"
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
        self.OUTPUT_FOLDER = parent_of_parent_dir + "/output/screenshots" 

    def readIntervals(self):
        """Read time intervals from a CSV file and return a list of tuples."""
        df = pd.read_csv(self.INTERVALS_FILE_PATH)
        intervals = [(row['start'], row['end']) for _, row in df.iterrows()]
        return intervals

    def captureScreenshot(self, folder_path, timestamp):
        """Capture a screenshot and save it to the specified folder with a timestamp."""
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        filename = f"{self.PLAYER_NAME}_{timestamp}.png"
        file_path = os.path.join(folder_path, filename)
        screenshot = pyautogui.screenshot()
        screenshot.save(file_path)
        #self.flashScreen()

    def flashScreen(self):
        """Flash the screen to indicate a screenshot has been taken."""
        root = tk.Tk()
        root.attributes('-fullscreen', True)
        root.configure(bg='black')
        root.attributes('-topmost', True)
        root.update()

        def close_flash():
            root.destroy()

        root.after(150, close_flash)  # Flash duration: 100 ms
        root.mainloop()

    # intervals are ordered chronologically from found battles
    def withinIntervals(self, current_time, intervals):
        """Check if the current time is within any of the specified intervals."""
        for start, end in intervals:
            start_time = datetime.strptime(start, "%H:%M:%S").time()
            end_time = datetime.strptime(end, "%H:%M:%S").time()
            if start_time <= current_time <= end_time:
                return True
        return False

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

    def startScreenshotting(self):
        intervals = self.readIntervals()

        self.countdown()
        start_time = datetime.now()
        last_time = datetime.strptime(intervals[-1][1], "%H:%M:%S").time()

        elapsed = None

        while True:
            
            self.prevent_lock_screen()
            
            elapsed = datetime.now() - start_time
            elapsed_time = (datetime.min + elapsed).time()  # Convert timedelta to time
            
            if elapsed_time > last_time:
                sys.exit()

            print("\nms: " + str(elapsed_time.microsecond))
            
            if self.withinIntervals(elapsed_time, intervals):
                self.captureScreenshot(self.OUTPUT_FOLDER, elapsed_time.strftime("%H-%M-%S"))
                print("screenshot taken at {} \n".format(elapsed_time))
                time.sleep(2)
            else:
                sleepTime = 1 - timedelta(microseconds=elapsed_time.microsecond).microseconds/1000000
                print("sleep time {}".format(str(sleepTime)))
                print("time now {}".format(datetime.now().time()))
                print("game time {}".format(elapsed_time))
                time.sleep(sleepTime)

def main():

    process = ScreeningProcess()
    process.startScreenshotting()

    pass

if __name__ == "__main__":

    main()
