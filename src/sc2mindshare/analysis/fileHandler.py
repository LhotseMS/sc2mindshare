"""Paths for the ported layer (CR-011): the legacy FileHandler's API, without its side effects.

The legacy FileHandler created folders under ``C:/MS SC`` when constructed and wrote the events
CSV, ``Intervals.csv`` and ``ImageTracking.csv``. Here it only answers paths and reads:

- the support files (``unitsInfo.csv``, ``upgradesInfo.csv``, ``ImageTracking.csv``) come from
  ``SOURCE_FOLDER``, which ``sc2mindshare.analysis.run`` sets (the project's ``MS SC/`` by default);
- ``intervalsFile`` never exists, so the detectors always take "pass 1" (no heatmaps, no uploads),
  and the intervals they would have written are kept in memory (``FileHandler.intervals``);
- nothing is ever written to disk.
"""

import csv
import os


class FileHandler:
    VIDEO_FILE_PREFIX = "Game"
    VIDEO_EXT = ".mp4"
    SOURCE_FOLDER = "MS SC"  # set by sc2mindshare.analysis.run.configure
    REPLAYS_FOLDER = SOURCE_FOLDER + "/Replays"

    IMAGES_END_FOLDER = "images"
    MAPS_END_FOLDER = "Maps"

    UPGRADES_INFO_FILE_NAME = "upgradesInfo.csv"
    UNITS_INFO_FILE_NAME = "unitsInfo.csv"
    INTERVALS_EXPORT_FILE_NAME = "Intervals.csv"
    IMAGE_TRACKING_FILE_NAME = "ImageTracking.csv"

    #: The pass-1 intervals text the battle detector produced last (instead of writing Intervals.csv).
    intervals = None

    def __init__(self, replay) -> None:
        self.player1 = replay.players[0]
        self.player2 = replay.players[1]

        self.gameName = "{}__{}_vs_{}".format(replay.map_name, self.player1, self.player2)

        self.gameFolder = "{}/{}".format(self.SOURCE_FOLDER, self.gameName)
        self.imagesFolder = "{}/{}".format(self.gameFolder, self.IMAGES_END_FOLDER)
        self.mapsFolder = "{}/{}".format(self.SOURCE_FOLDER, self.MAPS_END_FOLDER)

        self.eventsFile = None
        self.intervalsFile = "<no Intervals.csv: the new pipeline always runs pass 1>"

        self.unitInfoFile = "{}/{}".format(self.SOURCE_FOLDER, self.UNITS_INFO_FILE_NAME)
        self.ugradesInfoFile = "{}/{}".format(self.SOURCE_FOLDER, self.UPGRADES_INFO_FILE_NAME)

        self.imageTrackingFile = "{}/{}".format(self.SOURCE_FOLDER, self.IMAGE_TRACKING_FILE_NAME)

        self.player1VideoFileName = "{}_{}{}".format(self.VIDEO_FILE_PREFIX, self.player1, self.VIDEO_EXT)
        self.player2VideoFileName = "{}_{}{}".format(self.VIDEO_FILE_PREFIX, self.player2, self.VIDEO_EXT)

    def getImageTrackingFile(self):
        if not os.path.isfile(self.imageTrackingFile):
            return {}
        with open(self.imageTrackingFile, newline="", encoding="utf-8") as f:
            return {row["imageName"]: row["imageID"] for row in csv.DictReader(f)}

    def getPlayerVideoFileName(self, playerName):
        if playerName == self.player1.name:
            return self.player1VideoFileName
        elif playerName == self.player2.name:
            return self.player2VideoFileName
        else:
            return None

    def createEventsFile(self, contents):
        raise RuntimeError("the new pipeline writes no events CSV")

    def createIntervalsFile(self, contents):
        FileHandler.intervals = contents

    def createOrUpdateImageTrackingFile(self, newContents):
        raise RuntimeError("the new pipeline writes no ImageTracking.csv")
