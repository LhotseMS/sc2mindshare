import datetime
from sc2reader.events import *
from sc2reader.data import *
from sc2reader.events.tracker import UnitDiedEvent
from sc2reader.mindshare.battle import Battle, printDict
from sc2reader.mindshare.game import ControlGroup

from sc2reader.mindshare.mindshare import Base

from resources import Replay

locationDetector = None
controlGroupDetector = None
battleDetector = None

@staticmethod
def createDetectors(replay):
    locationDetector = BaseDetector(replay)
    battleDetector = BattleDetector(replay)
    #controlGroupDetector = ControlGroupDetector(replay)


class ControlGroupDetector():
    
    def __init__(self, replay, start = 0, finish = 1000000) -> None:
        
        self.CONTROL_GROUPS = {0:{},1:{}}
        
        x = 0 
        
        self.lastSelection = {0:list(),1:list()}
                
        for e in [v for v in replay.events if v.second >= start and v.second<= finish]:
            if x > 500:
                break
            
            #hold last selection event for a player
            #when control grp command comes create control group object

            # selection even is generated after the get control group occurs??! Check replay if selection happens or why is there a selection after a CG get
            
            if isinstance(e, SelectionEvent):
                self.lastSelection[e.pid].add(e)
            elif isinstance(e, SetControlGroupEvent):
                self.updateCG(e)
            elif isinstance(e, StealControlGroupEvent):
                self.removeUnitsFromOtherCGs(e)
                self.updateCG(e)


            x = x+1
            print(e)
        
        pass

    def removeUnitsFromOtherCGs(self, unitIDs):
        self = self

    def updateCG(self, e : SetControlGroupEvent):
        
        if e.control_group in self.CONTROL_GROUPS[e.pid]:
            self.CONTROL_GROUPS[e.pid][e.control_group].update(self.lastSelection[e.pid])
        else:
            self.CONTROL_GROUPS[e.pid][e.control_group] = ControlGroup(self.lastSelection[e.pid], e)
        
class BaseDetector():

    def __init__(self, replay):

        self.replay = replay
        self.player1 = self.replay.players[0]
        self.player2 = self.replay.players[1]

        self.locations = self.initDictByPlayer()

        self.findBases()
    
    def printLocations(self):
        printDict(self.locations)

    def findBases(self):
        basesBuiltEvents = [e for e in self.replay.events if isinstance(e, UnitInitEvent) and e.unit.is_building and e.unit._type_class.name in {"Nexus","Hatchery","OrbitalCommand"}]
        
        for e in basesBuiltEvents:
            self.processNewMainBase(e)

    def addNewBase(self, e):
        self.locations[e.player].append(Base(e, Base.BASE_NAMES_ORDER[len(self.locations[e.player])]))
        
    def processNewMainBase(self, e):
        
        for base in self.locations[e.player]:
            if base.location == e.location:
                base.newBase(e)
                return

        self.addNewBase(e)
    
    def getBaseOnLocation(self, e):

        basesOnLocation = list()
        for base in self.locations[e.player].items():
            if base.isLocationOnScreen(e.location):
                basesOnLocation.append(base)

        return basesOnLocation


    # TODO duplicate
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

class BattleDetector():

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
        unitDeathEvents = [e for e in self.replay.events if isinstance(e, UnitDiedEvent) and isinstance(e.unit.killing_unit, Unit) and e.countableDeath()] #not larva add drone deaths?
        
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