
import math


class Screen():
    
    SCREEN_SIZE = 15 #distance from the center to corner of the screen, exprimentaly determined
    
    def isLocationOnScreen(self, ex, ey, cx, cy, aspect_ratio=1.0):
        # Assume the rectangle's width to height ratio is w:h
        # Calculate width and height using the given distance d
        w = self.SCREEN_SIZE / math.sqrt(1 + (1/aspect_ratio)**2)
        h = w * aspect_ratio

        # Check bounds
        inside_x = (cx - w) <= ex <= (cx + w)
        inside_y = (cy - h) <= ey <= (cy + h)
        
        return inside_x and inside_y

class View(Screen):

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
            if self.isLocationOnScreen(event.x, event.y, c.x, c.y):
                return True
            
        return False
    

    # TODO consider location proximity computing functions on event
    def __str__(self) -> str:
        return f"Screen {self.firstView.location}-{self.lastView.location}:{len(self.vectors)}xE {self.duration}s"
    


class Base(Screen):

    BASE_NAMES_ORDER = ["Main base", "Natural", "3rd base", "4th base", "5th base", "6th base", "7th base"]

    def __init__(self, baseInitEvent, name):
        self.name = name
        self.bornEvevnt = baseInitEvent
        self.mainBase = baseInitEvent.unit
        self.vespene = []
        self.location = baseInitEvent.location

        self.isUp = True

    def newBase(self, e):
        self.isUp = True
        self.mainBase = e.unit
        self.location = e.location

    def __str__(self):
        return "{} {} at {}".format(self.name, self.mainBase, self.location) 
            
        
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
        
    

