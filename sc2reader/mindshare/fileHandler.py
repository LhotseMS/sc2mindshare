import os
import sc2reader
import pandas as pd

class FileHandler():

    VIDEO_FILE_PREFIX = "Game"
    VIDEO_EXT = ".mp4"
    SOURCE_FOLDER = "C:/MS SC"
    REPLAYS_FOLDER = SOURCE_FOLDER + "/Replays"

    IMAGES_END_FOLDER = "images"
    MAPS_END_FOLDER = "Maps"

    UPGRADES_INFO_FILE_NAME = "upgradesInfo.csv"
    UNITS_INFO_FILE_NAME = "unitsInfo.csv"
    INTERVALS_EXPORT_FILE_NAME = "Intervals.csv"
    IMAGE_TRACKING_FILE_NAME = "ImageTracking.csv"

    def __init__(self, replay) -> None:
        
        self.player1 = replay.players[0]
        self.player2 = replay.players[1]

        self.gameName = "{}__{}_vs_{}".format(replay.map_name, self.player1, self.player2)

        self.gameFolder = "{}/{}".format(self.SOURCE_FOLDER, self.gameName)
        self.imagesFolder = "{}/{}".format(self.gameFolder, self.IMAGES_END_FOLDER) 
        self.mapsFolder = "{}/{}".format(self.SOURCE_FOLDER, self.MAPS_END_FOLDER) 

        self.eventsFile = "{}/events_{}.csv".format(self.gameFolder, self.gameName)
        self.intervalsFile = "{}/{}".format(self.gameFolder, self.INTERVALS_EXPORT_FILE_NAME)

        self.unitInfoFile = "{}/{}".format(self.SOURCE_FOLDER, self.UNITS_INFO_FILE_NAME)
        self.ugradesInfoFile = "{}/{}".format(self.SOURCE_FOLDER, self.UPGRADES_INFO_FILE_NAME)
        
        self.imageTrackingFile = "{}/{}".format(self.SOURCE_FOLDER, self.IMAGE_TRACKING_FILE_NAME)

        self.player1VideoFileName = "{}_{}{}".format(self.VIDEO_FILE_PREFIX, self.player1, self.VIDEO_EXT)
        self.player2VideoFileName = "{}_{}{}".format(self.VIDEO_FILE_PREFIX, self.player2, self.VIDEO_EXT)

        if not os.path.exists(self.gameFolder):
            os.makedirs(self.gameFolder)

        if not os.path.exists(self.imagesFolder):
            os.makedirs(self.imagesFolder)
        
    def getImageTrackingFile(self):

        if os.path.isfile(self.imageTrackingFile):
            uploadedImagesTracker = {row['imageName']: row['imageID'] for _, row in pd.read_csv(self.imageTrackingFile).iterrows()}
        else:
            #TODO move to imageHandler
            self.createOrUpdateImageTrackingFile("imageName,imageID\n")
            uploadedImagesTracker = {}

        return uploadedImagesTracker

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

    def createOrUpdateImageTrackingFile(self, newContents):
        with open(self.imageTrackingFile, mode='a') as file:
            # Write the CSV string to the file
            file.write(newContents)