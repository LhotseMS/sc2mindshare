import datetime
from sc2reader.events import *
from sc2reader.events.tracker import UnitDiedEvent
from sc2reader.mindshare.battle import Battle, printDict
from sc2reader.mindshare.game import ControlGroup

from resources import Replay

class ControlGroupDetector():
    
    def __init__(self, replay : Replay) -> None:
        
        self.CONTROL_GROUPS = {0:{},1:{}}
        
        x = 0 
        
        self.lastSelection = {}
        
        for e in [v for v in replay.events]:
            if x > 500:
                break
            
            #hold last selection event for a player
            #when control grp command comes create control group object
            
            if isinstance(e,SelectionEvent):
                self.lastSelection[e.pid] = e
            
            #elif isinstance(e, SetControlGroupEvent):
            #    self.updateControlGroup(e)
                
            x = x+1
            print(e)
        
        pass

    def updateControlGroup(self, e : SetControlGroupEvent):
        
        if e.control_group in self.CONTROL_GROUPS[e.pid]:
            self.CONTROL_GROUPS[e.pid][e.control_group].update(self.lastSelection[e.pid])
        else:
            self.CONTROL_GROUPS[e.pid][e.control_group] = ControlGroup(self.lastSelection[e.pid], e)
        
    

class BattleDetector():
    
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
    
    @staticmethod
    def countableDeaths(e): 
        return isinstance(e, UnitDiedEvent) and e.unit.type not in [189,1075,158,431,108] and e.unit.is_army
            
    def findBattles(self):
        
        self.sortDeaths()
        
        battles = []
        self.battleStart = 0
        self.secondsOfBattle = []
                        
        for self.currentSecond, self.currentDeathEvents in self.deathsByTime.items():
            
            if self.battleStart == 0:
                self.battleStart = self.currentSecond
                print("AA")
                
            print(f"{datetime.timedelta(seconds=self.currentSecond)} - {datetime.timedelta(seconds=self.previousSecond)} - {datetime.timedelta(seconds=self.battleStart)}")
            
            if self.previousSecond != -1 and self.previousSecond + 2 < self.currentSecond:
                print("BB")
                battles.append(Battle(self.battleStart, self.previousSecond, self.replay, self.secondsOfBattle))
                self.resetBuffers()
                 
            if self.currentKeyFree >= 0 :
                self.fillBuffers()
            else:
                self.shiftBuffers()
                        
            self.secondsOfBattle.append(SecondOfaDying(self.currentSecond, self.currentDeathEvents, self.localCounts))  
            
            self.previousSecond = self.currentSecond
            #if battles.__len__() > 10:
                #break
            
        # print(battles[0])    
        for b in [t for t in battles if t.p1dc + t.p2dc > 10]:
            # if b.p1dc > 10 or b.p2dc > 10:
            getch()
            print(b)   
            
        return battles
    
    def sortDeaths(self):
        unitDeathEvents = [e for e in self.replay.events if BattleDetector.countableDeaths(e)] #not larva add drone deaths?
        
        self.deathsByTime = {}
        for e in unitDeathEvents:
            # time = int(e.frame / 16)
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
    


        
class SecondOfaDying():

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