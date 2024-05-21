import datetime
from sc2reader.events import *
from sc2reader.data import *
from sc2reader.events.tracker import UnitDiedEvent
from sc2reader.mindshare.battle import Battle, printDict
from sc2reader.mindshare.game import ControlGroup

from sc2reader.mindshare.mindshare import Base

from resources import Replay

basesDetector = None
controlGroupDetector = None
battleDetector = None

def createDetectors(replay):
    global basesDetector, battleDetector, controlGroupDetector
    #basesDetector = BaseDetector(replay)
    #battleDetector = BattleDetector(replay)
    controlGroupDetector = ControlGroupDetector(replay)

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

#TODO if there is events get cg select set cg count is as add to CG
class ControlGroupDetector(Detector):
    
    def __init__(self, replay) -> None:
        super().__init__(replay)
        
        self.CONTROL_GROUPS = self.initDictByPlayer(2)
        
        x = 0 
        
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
        
        print(self)

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
            self.CONTROL_GROUPS[e.player][e.control_group].update(self.lastSelection[e.player])
        else:
            self.CONTROL_GROUPS[e.player][e.control_group] = ControlGroup(self.lastSelection[e.player], e)

            
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
        
        print(self)
    
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

    def findBases(self):
        basesBuiltEvents = [e for e in self.replay.events if 
                            (isinstance(e, UnitInitEvent) or isinstance(e, UnitBornEvent))  
                            and e.unit.is_building 
                            and e.unit._type_class.name in {"Nexus","Hatchery","Hive","OrbitalCommand"} #main base unit born event has Hive for some reason
                            and self.isNearMinerals(e)]
        
        for e in basesBuiltEvents:
            self.processNewMainBase(e)

    def addNewBase(self, e):
        self.bases[e.player].append(Base(e, Base.BASE_NAMES_ORDER[len(self.bases[e.player])])) #TODO the base name logic should be in Base
        
    def processNewMainBase(self, e):
        
        print(e)
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
                
        self.findBattles()
        
        pass


    def findBattles(self):
        
        self.sortDeaths()
        
        battles = []
        self.battleStart = 0
        self.secondsOfBattle = []
                        
        for self.currentSecond, self.currentDeathEvents in self.deathsByTime.items():
            
            if self.battleStart == 0:
                self.battleStart = self.currentSecond
                # print("AA")
                
            # print(f"{datetime.timedelta(seconds=self.currentSecond)} - {datetime.timedelta(seconds=self.previousSecond)} - {datetime.timedelta(seconds=self.battleStart)}")
            
            if self.previousSecond != -self.LOWER_BOUND and self.previousSecond + self.UPPER_BOUND < self.currentSecond:
                # print("BB")
                battles.append(
                    Battle(
                        self.replay.players[0],
                        self.replay.players[1],
                        self.battleStart, 
                        self.previousSecond, 
                        [e for e in self.replay.events 
                            if e.second >= self.battleStart - self.LOWER_BOUND and 
                            e.second<= self.previousSecond + self.UPPER_BOUND] , 
                        self.secondsOfBattle))
                self.resetBuffers()
                 
            if self.currentKeyFree >= 0 :
                self.fillBuffers()
            else:
                self.shiftBuffers()
                        
            self.secondsOfBattle.append(SecondOfDying(self.currentSecond, self.currentDeathEvents, self.localCounts))  
            
            self.previousSecond = self.currentSecond
            #if battles.__len__() > 10:
                #break
            
        x = 0
        print(battles.__len__())    
        for b in [t for t in battles]: #  
            # if b.p1dc > 10 or b.p2dc > 10:

            print(b)
            x = x + 1
            
            #if x > 10:
             #   break
            getch()   
            
        return battles
    
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