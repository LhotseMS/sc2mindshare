import time
import pandas as pd
import pyautogui
import tkinter as tk
import os
from datetime import datetime, timedelta


# 1. Export battle times to game_battleID_intervals.csv
# 2. Read intervals make screenshots battle_player_second
# 3. Run export again reading the screenshots from a folder, 
# 4. assigninng screenshots names to battle images
# 5. upload images to mindshare picture
#

class ScreeningProcess():

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
        filename = f"screenshot_{timestamp}.png"
        file_path = os.path.join(folder_path, filename)
        screenshot = pyautogui.screenshot()
        screenshot.save(file_path)
        self.flashScreen()

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

    def prevent_lock_screen(self):
        """Move the mouse slightly every 'interval' seconds to prevent screen lock."""
        current_position = pyautogui.position()
        # Move the mouse by 1 pixel right and then back to avoid screen lock
        pyautogui.moveRel(10, 0)
        pyautogui.moveRel(-10, 0)

    # intervals are ordered chronologically from found battles
    def withinIntervals(self, current_time, intervals):
        """Check if the current time is within any of the specified intervals."""

        current_time = current_time.replace(microsecond=0)
        i_1_start = (datetime.strptime(intervals[0][0], "%H:%M:%S") - timedelta(seconds=self.INTERVAL_MARGIN)).time().replace(microsecond=0)
        i_1_end = (datetime.strptime(intervals[0][1], "%H:%M:%S") + timedelta(seconds=self.INTERVAL_MARGIN)).time().replace(microsecond=0)
             
        i_2_start = (datetime.strptime(intervals[1][0], "%H:%M:%S") - timedelta(seconds=self.INTERVAL_MARGIN)).time().replace(microsecond=0)
        i_2_end = (datetime.strptime(intervals[1][1], "%H:%M:%S") + timedelta(seconds=self.INTERVAL_MARGIN)).time().replace(microsecond=0)

        # if the time is in 1st interval confrim
        if i_1_start <= current_time <= i_1_end:
            return True
        # if the time is in 2nd, the time of the 1st one has passed, remove it and confirm 
        elif i_2_start <= current_time <= i_2_end:
            self.processedIntervals.append(intervals.pop(0))
            return True
        
        return False

    def countdown(self):
        """Display a countdown before starting the timer."""
        root = tk.Tk()
        root.overrideredirect(True)  # Remove window decorations
        root.geometry(self.COUNTDOWN_SIZE+self.COUNTDOWN_POSITION)  # Position the window

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

        previousEnd = datetime.now() - timedelta(seconds=1)
        currentEnd = datetime.now()
        elapsed = None


        while True:
            
            self.prevent_lock_screen()
            # TODO TODO TODO just cut down sleep by difference from the first MS one not from the previous
            # TODO there is an inherent delay probably caused by the algorithm that keeps delaying the 1s cycle eventually start slipping
            # by seconds, each iteration it slips about 200mcs
            elapsed = datetime.now() - start_time
            elapsed_time = (datetime.min + elapsed).time()  # Convert timedelta to time
            
            interval_duration = (currentEnd - previousEnd).total_seconds()
            previousEnd = currentEnd

            print("\n\nprevEnd: " + str(previousEnd))
            print("curEnd: " + str(currentEnd))
            
            if self.withinIntervals(elapsed_time, intervals):
                self.captureScreenshot(self.OUTPUT_FOLDER, elapsed_time.strftime("%H-%M-%S"))
                #print("screenshot taken\n")
                time.sleep(self.SCREENSHOT_INTERVAL)
            else:
                sleepTime = self.getSleepTime(interval_duration)
                self.endTimes.append(currentEnd)
                time.sleep(sleepTime)
                print("game time " + str(elapsed_time) + "  real time " + str(datetime.now()) + " sleep " + str(sleepTime))
                currentEnd = datetime.now()

    def getSleepTime(self, curntervalDuration):

        correlation = 0
        curDiff = 0
        prevDiff = 0

        if len(self.endTimes) > 3:
            prevDiff = self.endTimes[-2].microsecond - self.endTimes[-3].microsecond 
            curDiff = self.endTimes[-1].microsecond - self.endTimes[-2].microsecond 

        if curDiff > prevDiff:
            correlation = abs(curDiff - prevDiff)

        #print("cur" + str(curDiff))
        #print("prev" + str(prevDiff))
        #print("correlation:" + str(correlation))
        return 1 - abs(curntervalDuration - 1) - timedelta(microseconds= correlation).seconds


def main():

    process = ScreeningProcess()
    process.startScreenshotting()

    pass

if __name__ == "__main__":

    main()
