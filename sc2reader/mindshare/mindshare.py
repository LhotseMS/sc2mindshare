
import math
from sc2reader.events import *


class View():
    
    VIEW_SIZE = 15 #distance from the center to corner of the screen, exprimentaly determined
    
    def isLocationInView(self, ex, ey, vx, vy, aspect_ratio=1.0):
        # Assume the rectangle's width to height ratio is w:h
        # Calculate width and height using the given distance d
        w = self.VIEW_SIZE / math.sqrt(1 + (1/aspect_ratio)**2)
        h = w * aspect_ratio

        # Check bounds
        inside_x = (vx - w) <= ex <= (vx + w)
        inside_y = (vy - h) <= ey <= (vy + h)
        
        return inside_x and inside_y
    
class Screen(View):

    #TODO movement of camera across locations? is it upwards, up and down? from vectors
    SCREEN_RATIO = 30/22

    def __init__(self, cameraEvents, events = list()):
        self.cameraEvents = cameraEvents
        self.events = list()

        self.vectors = list()
        for i in range(len(self.cameraEvents) - 2):
            self.vectors.append((
                abs(self.cameraEvents[i].x - self.cameraEvents[i+1].x), 
                abs(self.cameraEvents[i].y - self.cameraEvents[i+1].y)))  
            
        for e in events:
            self.tryAddEvent(e)
        
        self.startTime = self.firstView.second
        self.endTime = self.lastView.second

    @property
    def duration(self):
        return self.endTime - self.startTime
    
    @property
    def firstView(self):
        return self.cameraEvents[0]
    
    @property
    def lastView(self):
        return self.cameraEvents[len(self.cameraEvents) - 1]
    
    def tryAddEvent(self, event) -> bool:
        if self.isEventOnScreen(event):
            self.events.append(event)
            return True

        return False

    def isEventOnScreen(self, event) -> bool:
        for c in self.cameraEvents:
            if self.isLocationInView(event.x, event.y, c.x, c.y):
                return True
            
        return False
    

    # TODO consider location proximity computing functions on event
    def __str__(self) -> str:
        return f"Screen {self.firstView.location}-{self.lastView.location}:{len(self.vectors)}xE {self.duration}s"
    

# TODO control groups to show the base name 
class Base(View):

    BASE_NAMES_ORDER = ["Main base", "Natural", "3rd base", "4th base", "5th base", "6th base", "7th base", "8th base", "9th base", "10th base", "11th base", "12th base", "13th base", "14th base", "15th base", "16th base"]

    #TODO check for when bases id destroyed
    def __init__(self, baseInitEvent : UnitInitEvent, order):
        
        # !!! CORRECTING and rewriting event unit name
        self.name = self.BASE_NAMES_ORDER[order]
        if order == 0 and self.name == "Hive":
            self.name = "Hatchery"
            baseInitEvent.unit.baseName = self.name
            baseInitEvent.unit.baseType = self.name
        else:
            baseInitEvent.unit.baseName = self.name
            baseInitEvent.unit.baseType = baseInitEvent.unit._type_class.name
            

        self.bornEvent = baseInitEvent
        self.raisedSec = baseInitEvent.second
        self.player = baseInitEvent.player
        self.race = baseInitEvent.player.pick_race
        self.base = baseInitEvent.unit
        self.vespene = []
        self.location = baseInitEvent.location

        self.isUp = True

    def newBase(self, e):
        self.isUp = True
        self.base = e.unit
        self.location = e.location

    def isLocationInBase(self, e):
        return self.raisedSec < e.second and self.isLocationInView(e.x, e.y, self.location[0], self.location[1])

    def minDistance(self, loc):
        return min(abs(self.location[0] - loc[0]),abs(self.location[1] - loc[1])) 

    def __str__(self):
        return "{}".format(self.name) 
            
        
class SecondOfaDying():

    def __init__(self, events, deathCount, deathProximity):
        self.events = events
        self.second = events.__len__()
        self.deathCount = deathCount
        self.deathProximity = deathProximity
        self.deathProximitySum = sum(deathProximity)
        self.dyingUnits = [e.unit for e in events]
        
    
    def __str__(self):
        return f"{self.second} : {self.deathCount} : {self.deathProximitySum} : {self.dyingUnits}"
        
    

