import datetime
from sc2reader.events import *
from sc2reader.data import *
from sc2reader.events.tracker import UnitDiedEvent
from sc2reader.mindshare.exports.link import UnitsLink
from sc2reader.mindshare.exports.battleNode import BattleNode
from sc2reader.mindshare.exports.upgradeNode import UpgradeNode 
from sc2reader.mindshare.exports.statsNode import StatsNode 
from sc2reader.mindshare.exports.buildingNode import BuildingNode 
from sc2reader.mindshare.exports.unitsNode import UnitsNode 
from sc2reader.mindshare.exports.messageNode import MessageNode 
from sc2reader.mindshare.battle import printDict 
from sc2reader.mindshare.game import ControlGroup

from sc2reader.mindshare.mindshare import Base
from sc2reader.mindshare.utils import MsUtils

from sc2reader.resources import Replay

basesDetector = None
controlGroupDetector = None
battleDetector = None
simpleDetector = None

def createDetectors(replay):
    global basesDetector, battleDetector, controlGroupDetector, simpleDetector

    # order is improtant as many use data set up by base controler or CGc
    basesDetector = BaseDetector(replay)
    controlGroupDetector = ControlGroupDetector(replay)
    battleDetector = BattleDetector(replay)
    simpleDetector = SimpleDetector(replay)

class Detector():
    # TODO duplicate declaration exists

    def __init__(self, replay) -> None:
        
        self.replay = replay
        self.player1 = self.replay.players[0]
        self.player2 = self.replay.players[1]

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

class SimpleDetector(Detector):
    
    OMIT_UNITS_UPGRADES = ("Reward","Spray","Game")
    OMIT_BUILDINGS = ("Creep","SupplyDepotLowered")
    OMIT_UNITS = ("Larva", "Broodling","Shield battery","Extractor Rich","Egg","SiegeTankSieged","InfestorBurrowed","RefineryRich","ParasiticBombDummy")
    STATS_TIMES = ("01.04","02.08","03.12","04.17","05.21","06.25","07.30","08.34","09.38","10.42","11.47","12.58","14.02","15.07","16.11","17.16")

    UNIT_INTERVAL = 10

    def __init__(self, replay) -> None:

        self.replay = replay
        self.player1 = self.replay.players[0]
        self.player2 = self.replay.players[1]

        self.links = list()

        self.upgradesByPlayer = self.initDictByPlayer()
        self.statsByPlayer = self.initDictByPlayer()
        self.buildingsByPlayer = self.initDictByPlayer()
        self.unitsByPlayerAndType = self.initDictByPlayer()
        
        self.lastUnitsByType = self.initDictByPlayer(2)
        self.messagesByPlayer = self.initDictByPlayer()

        #before findSimpleNodes 
        self.buildingNameIndex = {}
        
        #self.unitIntervalStart = "00:00"
        self.currentIntervalEvents = self.initDictByPlayer(2)
        
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

        for e in [v for v in self.replay.events if 
                  (isinstance(v, UpgradeCompleteEvent) or 
                   isinstance(v, PlayerStatsEvent) or 
                   isinstance(v, UnitBornEvent) or 
                   isinstance(v, UnitDoneEvent) or
                   isinstance(v, MessageEvent))]:
            
            if isinstance(e, UpgradeCompleteEvent) and self.upgradeEligible(e):
                upgradeCounter += 1
                self.upgradesByPlayer[e.player].append(UpgradeNode(e, upgradeCounter))
            elif isinstance(e, PlayerStatsEvent) and self.statsEligible(e):
                statsCounter += 1
                self.statsByPlayer[e.player].append(StatsNode(e, statsCounter))
            elif isinstance(e, UnitDoneEvent) and self.buildingsEligible(e):
                buildingCounter += 1
                self.addBuilding(e, buildingCounter)
            #elif isinstance(e, MessageEvent):
            #    self.messagesByPlayer[e.player].append(MessageNode(e))
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

                            unitsCounter += 1
                            node = UnitsNode(events, "00:" + currentInterval, unitsCounter)
                            nodeUnitType = node.getNodeName()

                            self.unitsByPlayerAndType[player].append(node)

                            if nodeUnitType in self.lastUnitsByType[player]:
                                self.addLink(self.lastUnitsByType[player][nodeUnitType], node) 

                            self.lastUnitsByType[player][nodeUnitType] = node
                    
                    self.currentIntervalEvents = self.initDictByPlayer(2)
                    currentInterval = newInterval

                    self.addUnit(e)

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
class ControlGroupDetector(Detector):
    
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

            # selection even is generated after the get control group occurs??! Check replay if selection happens or why is there a selection after a CG get
            
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
        return self.CONTROL_GROUPS[player][cgNo].getUnits(second)

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
        
class BaseDetector(Detector):

    DISTANCE_FROM_MINERALS = 5

    def __init__(self, replay):

        self.replay = replay
        self.player1 = self.replay.players[0]
        self.player2 = self.replay.players[1]

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

class BattleDetector(Detector):

    LOWER_BOUND = 2
    UPPER_BOUND = 2
    
    def __init__(self, replay):
        
        self.currentSecond = 0
        self.battleStart = 0
        self.resetBuffers()
        self.replay = replay
        
        self.currentSecond = None
        self.currentDeathEvents = []
        self.deathsByTime = {}
        self.previousSecond = -1
                
        self.battles = []   
        self.findBattles()
        
        pass

    # TODO add Unit initiated Shield Battery
    def findBattles(self):
        
        self.sortDeaths()
        
        self.battleStart = 0
        self.secondsOfBattle = []
                        
        for self.currentSecond, self.currentDeathEvents in self.deathsByTime.items():
            
            if self.battleStart == 0:
                self.battleStart = self.currentSecond
                # print("AA")
                
            # print(f"{datetime.timedelta(seconds=self.currentSecond)} - {datetime.timedelta(seconds=self.previousSecond)} - {datetime.timedelta(seconds=self.battleStart)}")
            
            if self.previousSecond != -self.LOWER_BOUND and self.previousSecond + self.UPPER_BOUND < self.currentSecond:
                # print("BB")
                self.battles.append(
                    BattleNode(
                        self.replay.players[0],
                        self.replay.players[1],
                        self.battleStart, 
                        self.previousSecond, 
                        [e for e in self.replay.events 
                            if e.second >= self.battleStart - self.LOWER_BOUND and 
                            e.second<= self.previousSecond + self.UPPER_BOUND] , 
                        self.secondsOfBattle,
                        len(self.battles)))
                self.resetBuffers()
                 
            if self.currentKeyFree >= 0 :
                self.fillBuffers()
            else:
                self.shiftBuffers()
                        
            self.secondsOfBattle.append(SecondOfDying(self.currentSecond, self.currentDeathEvents, self.localCounts))  
            
            self.previousSecond = self.currentSecond
            #if battles.__len__() > 10:
                #break
        
        self.battles.pop(0)
        x = 0
        #print(battles.__len__())    
        #for b in [t for t in battles]: #  
            # if b.p1dc > 10 or b.p2dc > 10:

         #   print(b)
          #  x = x + 1
            
            #if x > 10:
             #   break
           # getch()   
    
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
       
        
    # printDict(deathsByTime, "Deaths")
        
    # if 
       
    
    
    # for a,value in replay.datapack.abilities.items():
    #     if value.is_build:
    #         pprint(f"{a}, {value.}")
    # print(deathsByTime[537][0].unit.type)
    


        
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