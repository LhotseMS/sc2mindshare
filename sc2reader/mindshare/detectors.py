import datetime
import os
import pandas as pd
from datetime import datetime, timedelta

from sc2reader.events import *
from sc2reader.data import *
from sc2reader.events.tracker import UnitDiedEvent
from sc2reader.mindshare.exports.link import BattleLink, UnitsLink, StatsLink, UpgradeLevelLink, UpgradeEqLink, gpLink
from sc2reader.mindshare.exports.battleNode import BattleNode
from sc2reader.mindshare.exports.upgradeNode import UpgradeNode 
from sc2reader.mindshare.exports.statsNode import StatsNode 
from sc2reader.mindshare.exports.buildingNode import BuildingNode 
from sc2reader.mindshare.exports.unitsNode import UnitsNode 
from sc2reader.mindshare.exports.chatNode import ChatNode 
from sc2reader.mindshare.exports.gameNode import GameNode 
from sc2reader.mindshare.exports.playerNode import PlayerNode 
from sc2reader.mindshare.battle import printDict 
from sc2reader.mindshare.game import ControlGroup

from sc2reader.mindshare.mindshare import Base
from sc2reader.mindshare.utils import MsUtils

from sc2reader.resources import Replay
from sc2reader.mindshare.fileHandler import FileHandler
from sc2reader.mindshare.imageUploader import ImageUploader

basesDetector = None
controlGroupDetector = None
battleDetector = None
simpleDetector = None
singlesDetector = None

def createDetectors(replay):
    global basesDetector, battleDetector, controlGroupDetector, simpleDetector, singlesDetector

    # order is improtant as many use data set up by base controler or CGc
    basesDetector = BaseDetector(replay)
    controlGroupDetector = ControlGroupDetector(replay)
    battleDetector = BattleDetector(replay)
    simpleDetector = SimpleDetector(replay)
    singlesDetector = SinglesDetector(replay)

class SinglesDetector():
    
    def __init__(self, replay) -> None:

        self.nodes = list()
        self.links = list()
    
        g = GameNode(replay)
        p1 = PlayerNode(replay.players[0], replay.players[1],1)
        p2 = PlayerNode(replay.players[1], replay.players[0],2)

        self.nodes.append(g)
        self.nodes.append(p1)
        self.nodes.append(p2)

        self.links.append(gpLink(g,p1))
        self.links.append(gpLink(g,p2))

        #TODO add links

class EventsDetector():
    # TODO duplicate declaration exists

    def __init__(self, replay) -> None:
        
        self.replay = replay
        self.player1 = self.replay.players[0]
        self.player2 = self.replay.players[1]

        self.fh = FileHandler(replay)

    def initDictByPlayer(self, type = 1):
        d = {}

        if type == 0:
            d[self.player1] = 0 
            d[self.player2] = 0
        elif type == 1:
            d[self.player1] = list()
            d[self.player2] = list()
        elif type == 2:
            d[self.player1] = {}
            d[self.player2] = {}

        return d

    def otherPlayer(self, player):
        return self.player2 if player == self.player1 else self.player1

class SimpleDetector(EventsDetector):
    
    OMIT_UNITS_UPGRADES = ("Reward","Spray","Game")
    OMIT_BUILDINGS = ("Creep","SupplyDepotLowered")
    OMIT_UNITS = ("Larva", "Broodling","Shield battery","Extractor Rich","Egg","SiegeTankSieged","InfestorBurrowed","RefineryRich","ParasiticBombDummy","InvisibleTargetDummy")
    STATS_TIMES = ("01.04","02.08","03.12","04.17","05.21","06.25","07.30","08.34","09.38","10.42",
                   "11.47","12.58","14.02","15.07","16.11","17.14","18.20","19.24","20.28","21.32",
                   "22.36","23.40","24.45","25.57","27.01","28.05","29.17","30.21","32.25","32.30","33.34",
                   "34.38","35.42","36.47","37.51")

    UNIT_INTERVAL = 10

    def __init__(self, replay) -> None:
        super().__init__(replay)

        self.links = list()

        self.upgradesByPlayer = self.initDictByPlayer()
        self.statsByPlayer = self.initDictByPlayer()
        self.buildingsByPlayer = self.initDictByPlayer()
        self.unitsByPlayerAndType = self.initDictByPlayer()
        
        self.lastUnitsByType = self.initDictByPlayer(2)
        self.unitTypeCount = self.initDictByPlayer(2)
        self.messagesByPlayer = self.initDictByPlayer()

        #before findSimpleNodes 
        self.buildingNameIndex = {}
        
        #self.unitIntervalStart = "00:00"
        self.currentIntervalEvents = self.initDictByPlayer(2)
        self.previousUpgradeLevels = self.initDictByPlayer(2)
        self.upgradesByLevels = {}
        
        # simple nodes are the ones that are 1:1 with events and don't need too much post processing
        self.findSimpleNodes()

        #after findSimpleNodes
        self.upgrades = self.upgradesByPlayer[self.player1] + self.upgradesByPlayer[self.player2]
        self.stats = self.statsByPlayer[self.player1] + self.statsByPlayer[self.player2]
        self.buildings = self.buildingsByPlayer[self.player1] + self.buildingsByPlayer[self.player2]
        self.units = self.unitsByPlayerAndType[self.player1] + self.unitsByPlayerAndType[self.player2]
        self.messages = self.messagesByPlayer[self.player1] + self.messagesByPlayer[self.player2]

    def findSimpleNodes(self):

        #unit detection variables
        currentInterval = "00:00"
        upgradeCounter = 0
        statsCounter = 0
        buildingCounter = 0
        unitsCounter = 0
        chatCounter = 0

        # TODO add message event as for messages in lobby?
        for e in [v for v in self.replay.events if 
                  (isinstance(v, UpgradeCompleteEvent) or 
                   isinstance(v, PlayerStatsEvent) or 
                   isinstance(v, UnitBornEvent) or 
                   isinstance(v, UnitDoneEvent) or 
                   isinstance(v, ChatEvent) or 
                   isinstance(v, UnitDiedEvent))]:
            
            if isinstance(e, UpgradeCompleteEvent) and self.upgradeEligible(e):
                upgradeCounter += 1

                newNode = UpgradeNode(e, upgradeCounter)
                self.upgradesByPlayer[e.player].append(newNode)

                if newNode.subtype in self.previousUpgradeLevels[e.player]:
                    self.links.append(UpgradeLevelLink(self.previousUpgradeLevels[e.player][newNode.subtype], newNode))

                if newNode.level != None:
                    #TODO setting up the dict might be a candidate for move
                    if newNode.level not in self.upgradesByLevels:
                        self.upgradesByLevels[newNode.level] = {}
                    if newNode.interaction not in self.upgradesByLevels[newNode.level]:
                        self.upgradesByLevels[newNode.level][newNode.interaction] = list()
                        
                    self.upgradesByLevels[newNode.level][newNode.interaction].append(newNode)

            elif isinstance(e, PlayerStatsEvent) and self.statsEligible(e):
                statsCounter += 1
                self.statsByPlayer[e.player].append(StatsNode(e, statsCounter))

                #TODO adding links should be in a separate class probably just as adding nodes
                if (e.player in self.statsByPlayer and
                    len(self.statsByPlayer[e.player]) == len(self.statsByPlayer[self.otherPlayer(e.player)])):
                    self.links.append(StatsLink(self.statsByPlayer[e.player][-1], 
                                                self.statsByPlayer[self.otherPlayer(e.player)][-1]))

            elif isinstance(e, UnitDoneEvent) and self.buildingsEligible(e):
                buildingCounter += 1
                self.addBuilding(e, buildingCounter)
            elif isinstance(e, ChatEvent):
                chatCounter += 1
                self.messagesByPlayer[e.player].append(ChatNode(e, chatCounter, str(e.player)))
            elif isinstance(e, UnitDiedEvent):
                if e.player != None and e.unit.nameC in self.unitTypeCount[e.player]:
                    self.unitTypeCount[e.player][e.unit.nameC] -= 1            
            elif ((isinstance(e, UnitBornEvent) or 
                  isinstance(e, UnitDoneEvent)) and
                  self.unitEligble(e)):
                
                newInterval = self.getNearestIntervalStart(e.time)

                # same interval, add unit
                if currentInterval == newInterval:
                    self.addUnit(e)
                else:
                    for player, types in self.currentIntervalEvents.items():
                        for type, events in types.items():

                            # init the node with all events that have been captured for given type
                            unitsCounter += 1
                            node = UnitsNode(events, "00:" + currentInterval, unitsCounter)
                            nodeUnitType = node.name

                            # iterate unit type count
                            if not nodeUnitType in self.unitTypeCount[player]:
                                self.unitTypeCount[player][nodeUnitType] = 0

                            # set unit count type
                            self.unitTypeCount[player][nodeUnitType] += node.count
                            node.setCurrenCount(self.unitTypeCount[player][nodeUnitType])

                            self.unitsByPlayerAndType[player].append(node)

                            # save last unit node by type for links and create links
                            if nodeUnitType in self.lastUnitsByType[player]:
                                self.addLink(self.lastUnitsByType[player][nodeUnitType], node) 

                            self.lastUnitsByType[player][nodeUnitType] = node
                    
                    self.currentIntervalEvents = self.initDictByPlayer(2)
                    currentInterval = newInterval

                    self.addUnit(e)

        #create upgrade links
        for level in self.upgradesByLevels:
            if level != None:
                for interaction in enumerate(self.upgradesByLevels[level]):
                        if interaction != None:
                            for i, node in enumerate(self.upgradesByLevels[level][interaction[1]]):
                                for j, otherNode in enumerate(self.upgradesByLevels[level][interaction[1]]):
                                    if i < j:
                                        self.links.append(UpgradeEqLink(node, otherNode))

    # TODO seems like no units are being found

    def addLink(self, n1, n2):
        self.links.append(UnitsLink(n1, n2))

    def upgradeEligible(self, e) -> bool:
        return not str(e.upgrade_type_name).startswith(self.OMIT_UNITS_UPGRADES)
    
    def statsEligible(self, e) -> bool:
        return e._str_prefix().strip().endswith(self.STATS_TIMES)
    
    def buildingsEligible(self, e) -> bool:
        return not str(e.unit).startswith(self.OMIT_BUILDINGS) and e.unit.is_building

    def unitEligble(self, e) -> bool:
        return (e.player != None and
                not e.unit.is_building and 
                not e.time == "00:00" and 
                not e.unit.name.startswith(self.OMIT_UNITS))

    def addBuilding(self, e, seq):
        node = BuildingNode(e, seq)
        node.index = self.getBuildingIndex(node)
        self.buildingsByPlayer[e.player].append(node)

    # TODO building are indexed across both players should be per player
    def getBuildingIndex(self, node) -> int:

        buildingName = node.getNodeName()
        
        # append building index so that building dont have the same name
        if self.buildingNameIndex.get(buildingName) == None:
            self.buildingNameIndex[buildingName] = 0
        else:
            self.buildingNameIndex[buildingName] = self.buildingNameIndex[buildingName] + 1

        return self.buildingNameIndex[buildingName]
    
    def addUnit(self, e):
        try:
            if not e.unit.name in self.currentIntervalEvents[e.player]:
                self.currentIntervalEvents[e.player][e.unit.name] = list()

            self.currentIntervalEvents[e.player][e.unit.name].append(e)
    
        except Exception:
            print(e.__class__())


    def shiftUnitsInterval(self):
        self.unitIntervalStart = MsUtils.incrementSeconds(self.unitIntervalStart, self.UNIT_INTERVAL)
        self.unitIntervalEnd = MsUtils.incrementSeconds(self.unitIntervalEnd, self.UNIT_INTERVAL)
        self.currentIntervalEvents = self.initDictByPlayer(2)

    def getNearestIntervalStart(self, timeStr) -> str:
        minutes, seconds = map(int, timeStr.split(':'))
        totalSeconds = minutes * 60 + seconds
        
        nearestInterval = round(totalSeconds / 10) * 10
        
        nearestMin = nearestInterval // 60
        nearestSec = nearestInterval % 60
        
        # Format the result as MM:SS
        return f"{nearestMin:02}:{nearestSec:02}"        
        

#TODO if there is events get cg select set cg count is as add to CG
class ControlGroupDetector(EventsDetector):
    
    def __init__(self, replay) -> None:
        super().__init__(replay)
        
        self.CONTROL_GROUPS = self.initDictByPlayer(2)
                
        self.lastSelection = {}
        self.lastGetEvent = {0:None, 1:None}

        #TODO ideally there should be one big loop and detector should be called per event
        for e in [e for e in replay.events if 
                  isinstance(e, SelectionEvent) or  
                  isinstance(e, StealControlGroupEvent) or 
                  isinstance(e, AddToControlGroupEvent) or 
                  isinstance(e, SetControlGroupEvent) or 
                  isinstance(e, GetControlGroupEvent) or 
                  isinstance(e, TargetPointCommandEvent) or 
                  isinstance(e, UnitDiedEvent) or 
                  isinstance(e, TargetUnitCommandEvent)]:
            
            #hold last selection event for a player
            #when control grp command comes create control group object

            # selection event is generated after the get control group occurs??! Check replay if selection happens or why is there a selection after a CG get
            
            if isinstance(e, SelectionEvent) and e.new_units:
                self.lastSelection[e.player] = e
            elif isinstance(e, SetControlGroupEvent):
                self.updateCG(e)
            elif isinstance(e, StealControlGroupEvent):
                self.removeUnitsFromOtherCGs(e.player, "")
                self.updateCG(e)
            elif isinstance(e, GetControlGroupEvent):
                self.lastGetEvent[e.player] = e
        

    def getCgUnits(self, player, cgNo, second):

        if cgNo in self.CONTROL_GROUPS[player]:
            return self.CONTROL_GROUPS[player][cgNo].getUnits(second)
        else:
            return None

    def addActionToCG(self, e):
        pass

    def removeUnitsFromOtherCGs(self, player, unitIDs):
        pass
       # for id in unitIDs:
            #self.CONTROL_GROUPS[player].

    def updateCG(self, e : SetControlGroupEvent):
        
        if e.control_group in self.CONTROL_GROUPS[e.player]:
            self.CONTROL_GROUPS[e.player][e.control_group].addUnits(e, self.lastSelection[e.player])
        else:
            self.CONTROL_GROUPS[e.player][e.control_group] = ControlGroup(e, self.lastSelection[e.player])

            
    def __str__(self) -> str:
        for player, cgs in self.CONTROL_GROUPS.items():
            for cgNo, cg in cgs.items():
                print(cg)
        return ""
        
class BaseDetector(EventsDetector):

    DISTANCE_FROM_MINERALS = 5

    def __init__(self, replay):
        super().__init__(replay)

        self.mineralLocations = list()
        self.bases = self.initDictByPlayer()

        self.findMinerals()
        self.findBases()
    
    def printLocations(self):
        printDict(self.bases)

    def findMinerals(self):
        mineralEvents = [e for e in self.replay.events if isinstance(e, UnitBornEvent)]

        for me in mineralEvents:
            if "mineral" in me.unit.name or "Mineral" in me.unit.name:
                self.mineralLocations.append(me.location)

    def isNearMinerals(self, e):
        return len([ml for ml in self.mineralLocations if 
                    abs(ml[0] - e.x) < self.DISTANCE_FROM_MINERALS or 
                    abs(ml[1] - e.y) < self.DISTANCE_FROM_MINERALS]) > 0

    def isBase(self, unit):
        return unit.is_building and unit._type_class.name in {"Nexus","Hatchery","Hive","OrbitalCommand"} #main base unit born event has Hive for some reason
                            
    def findBases(self):
        basesBuiltEvents = [e for e in self.replay.events if 
                            (isinstance(e, UnitInitEvent) or isinstance(e, UnitBornEvent))  
                            and self.isBase(e.unit)
                            and self.isNearMinerals(e)]
        
        for e in basesBuiltEvents:
            self.processNewMainBase(e)

    def addNewBase(self, e):
        
        #TODO the base name logic should be in Base
        #workaround as 1st zerg base is named Hive for some reason
            
        self.bases[e.player].append(Base(e, len(self.bases[e.player]))) 
        
    def processNewMainBase(self, e):
        
        for base in self.bases[e.player]:
            if base.location == e.location:
                print("THIS GOT TRIGGERED?! Base dies?")
                base.newBase(e)
                return

        self.addNewBase(e)
    

    # bases might not exist yet
    def getBaseOnLocation(self, e) -> Base:

        minDistBase = None
        minDistance = 1000
        for player, bases in self.bases.items():
            for base in bases:
                if base.isLocationInBase(e):
                    dist = base.minDistance(e.location) < minDistance
                    if dist < minDistance:
                        minDistBase = base
                        minDistance = dist

        return minDistBase

    def __str__(self) -> str:
        printDict(self.bases)
        return ""

class BattleDetector(EventsDetector): 

    BATTLE_LOWER_BOUND = 3
    BATTLE_UPPER_BOUND = 4
    INTERVAL_LOWER_BOUND = 2
    INTERVAL_UPPER_BOUND = 2
    INTERVALS_FILE_HEADER = "start,end,id\n"

    def __init__(self, replay):
        super().__init__(replay)
        
        self.iu = ImageUploader()

        self.currentSecond = 0
        self.battleStart = 0
        self.resetBuffers()
        
        self.currentSecond = None
        self.currentDeathEvents = []
        self.deathsByTime = {}
        self.previousSecond = -1

        self.links = list() 
        self.battles = []   
        self.findBattles()
        
        self.screenshotsDict = None

        if os.path.exists(self.fh.intervalsFile):
            self.addScreenshotsToBattles()
        else:
            self.createBattleIntervals()

    # TODO add Unit initiated Shield Battery
    def findBattles(self):
        
        self.sortDeaths()
        
        self.battleStart = 0
        self.secondsOfBattle = []
                        
        for self.currentSecond, self.currentDeathEvents in self.deathsByTime.items():
            
            if self.battleStart == 0:
                self.battleStart = self.currentSecond
                
            if self.previousSecond != -self.BATTLE_LOWER_BOUND and self.previousSecond + self.BATTLE_UPPER_BOUND < self.currentSecond:
                # print("BB")
                self.battles.append(
                    BattleNode(
                        self.player1,
                        self.player2,
                        self.battleStart, 
                        self.previousSecond, 
                        [e for e in self.replay.events 
                            if e.second >= self.battleStart - self.BATTLE_LOWER_BOUND and 
                            e.second<= self.previousSecond + self.BATTLE_UPPER_BOUND], 
                        self.secondsOfBattle,
                        len(self.battles)))
                
                if len(self.battles) > 2:
                    self.links.append(BattleLink(self.battles[-2],self.battles[-1]))

                self.resetBuffers()
                 
            if self.currentKeyFree >= 0 :
                self.fillBuffers()
            else:
                self.shiftBuffers()
                        
            self.secondsOfBattle.append(SecondOfDying(self.currentSecond, self.currentDeathEvents, self.localCounts))
            
            self.previousSecond = self.currentSecond
            #if battles.__len__() > 10:
                #break
        
        #for some reason there is a 00 empty battle at the start TODO?
        self.battles.pop(0) 
    
    def createBattleIntervals(self):

        gameBattlesIntervalsStr = self.INTERVALS_FILE_HEADER

        for battle in self.battles:
            gameBattlesIntervalsStr += "{},{},{}\n".format(battle.startTime - timedelta(seconds=self.INTERVAL_LOWER_BOUND), 
                                                           battle.endTime + timedelta(seconds=self.INTERVAL_LOWER_BOUND), battle.getNodeID())

        self.fh.createIntervalsFile(gameBattlesIntervalsStr)

    def initScreenshotsDict(self):
        self.screenshotsDict = {}
        for battle in self.battles:
            self.screenshotsDict[battle.getNodeID()] = list()

    def addScreenshotsToBattles(self):        
        self.initScreenshotsDict()
        self.uploadScreenshotsToMediaServer()

        for battle in self.battles:
            for imageID in self.screenshotsDict[battle.getNodeID()]:
                battle.addImage("{}{}".format(ImageUploader.RESOURCE_URL, imageID))

    def uploadScreenshotsToMediaServer(self):
        pngScreenshots = [file for file in os.listdir(self.fh.screenshotsFolder) if file.endswith('.png')]

        if os.path.isfile(self.fh.imageTrackingFile):
            newlyUploadedImages = ""
            uploadedImagesDict = self.readTrackedImageFile()
        else:
            #TODO move to imageHandler
            newlyUploadedImages = "imageName,imageID\n"
            uploadedImagesDict = {}

        for screenshotName in pngScreenshots:
            battleID = screenshotName.split("_")[0]
            imageID = None

            # if the image has already been uploaded
            if screenshotName in uploadedImagesDict:
                imageID = uploadedImagesDict[screenshotName]
                print("image {} existing as {}".format(screenshotName, imageID))
            else:
                uploadInfo = self.iu.uploadImage(self.fh.screenshotsFolder, screenshotName)
                imageID = uploadInfo["id"]

                if uploadInfo["status"] == 201:
                    newlyUploadedImages += "{},{}\n".format(screenshotName, uploadInfo["id"])
                    print("image {} uploaded as {}".format(screenshotName, uploadInfo["id"]))
                else:
                    print("Failed to upload file {}, status {}".format(screenshotName, uploadInfo["status"]))

            self.screenshotsDict[battleID].append(imageID)

        self.fh.createOrUpdateImageTrackingFile(newlyUploadedImages)

    #TODO move all file reading to the file handler class
    def readTrackedImageFile(self):
        df = pd.read_csv(self.fh.imageTrackingFile)
        return {row['imageName']: row['imageID'] for _, row in df.iterrows()}

    def sortDeaths(self):
        # TODO the logic for identifying eligible UD events is all over the place, 3x?
        unitDeathEvents = [e for e in self.replay.events if isinstance(e, UnitDiedEvent) and isinstance(e.unit.killing_unit, Unit) and e.countableUnitDeath()] #not larva add drone deaths?
        
        self.deathsByTime = {}
        for e in unitDeathEvents:
            
            if self.deathsByTime.get(e.second) == None:
                self.deathsByTime[e.second] = list()
            self.deathsByTime[e.second].append(e)
            
    
    def shiftArray(self, array, new): 
        array[4] = array[3]
        array[3] = array[2]
        array[2] = array[1]
        array[1] = array[0] 
        array[0] = new
        return array

    def resetBuffers(self):
        self.localCounts = [0,0,0,0,0]
        self.currentKeys = [-1,-1,-1,-1,-1]
        self.currentKeyFree = 4
        self.secondsOfBattle = []
        self.battleStart = self.currentSecond

    def fillBuffers(self):
        self.currentKeys[self.currentKeyFree] = self.currentSecond 
        self.localCounts[self.currentKeyFree] = self.currentDeathEvents.__len__()
        self.currentKeyFree = self.currentKeyFree - 1 
        
    def shiftBuffers(self):
        self.shiftArray(self.currentKeys,self.currentSecond)
        self.shiftArray(self.localCounts,self.currentDeathEvents.__len__())
               
class SecondOfDying():

    def __init__(self, sec, events, deathProximity):
        self.events = events
        self.second = sec
        self.deathCount = events.__len__()
        self.deathProximity = deathProximity
        self.deathProximitySum = sum(deathProximity)
        self._dyingUnits = [e.unit for e in events]
        
    @property
    def dyingUnits(self):
        return self._dyingUnits
    
    def __str__(self):
        return f"{self.second} : {self.deathCount} : {self.deathProximitySum} : {self.dyingUnits}"
            
            
            
try:
    # Assume that we are on *nix or Mac
    import termios
    import fcntl
    import os
    import sys

    def getch():
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
        try:
            while 1:
                try:
                    sys.stdin.read(1)
                    break
                except OSError:
                    pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
            
except ImportError as e:
    try:
        # Oops, we might be on windows, try this one
        from msvcrt import getch
    except ImportError as e:
        # We can't make getch happen, just dump events to the screen
        getch = lambda: True