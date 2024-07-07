import os
import sc2reader

class FileHandler():

    VIDEO_FILE_PREFIX = "Game"
    VIDEO_EXT = ".mp4"
    SOURCE_FOLDER = "C:/MS SC"
    INTERVALS_EXPORT_FILE = "Intervals.csv"
    SCREENSHOTS_END_FOLDER = "screenshots"
    REPLAYS_FOLDER = SOURCE_FOLDER + "/Replays"

    def __init__(self, replay) -> None:
        
        self.player1 = replay.players[0]
        self.player2 = replay.players[1]

        self.gameName = "{}__{}_vs_{}".format(replay.map_name, self.player1, self.player2)

        self.gameFolder = "{}/{}".format(self.SOURCE_FOLDER, self.gameName)
        self.screenshotsFolder = "{}/{}".format(self.gameFolder, self.SCREENSHOTS_END_FOLDER) 

        self.eventsFile = "{}/events_{}.csv".format(self.gameFolder, self.gameName)
        self.intervalsFile = "{}/{}".format(self.gameFolder, self.INTERVALS_EXPORT_FILE)

        self.player1VideoFileName = "{}_{}{}".format(self.VIDEO_FILE_PREFIX, self.player1, self.VIDEO_EXT)
        self.player2VideoFileName = "{}_{}{}".format(self.VIDEO_FILE_PREFIX, self.player2, self.VIDEO_EXT)

        if not os.path.exists(self.gameFolder):
            os.makedirs(self.gameFolder)

        if not os.path.exists(self.screenshotsFolder):
            os.makedirs(self.screenshotsFolder)
        
    def getPlayerVideoFileName(self, playerName):
        if playerName == self.player1.name:
            return self.player1VideoFileName
        elif playerName == self.player2.name:
            return self.player2VideoFileName
        #TODO throw error maybe
        else:
            return None
        
    def createEventsFile(self, contents):
        with open(self.eventsFile, mode='w') as file:
        # Write the CSV string to the file
            file.write(contents)

    def createIntervalsFile(self, contents):
        with open(self.intervalsFile, mode='w') as file:
            # Write the CSV string to the file
            file.write(contents)