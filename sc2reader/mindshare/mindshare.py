
class Battle():
    """
    This event is recorded for each player at the very beginning of the game before the
    :class:`GameStartEvent`.
    """

    def __init__(self, startSec, endSec, replay, events):
        #:
        self.startSec = startSec
        self.endSec = endSec
        self.replay = replay
              
        
class SecondOfaDying():

    def __init__(self, events, deathCount, deathProximity):
        self.events = events
        self.second = events.__len__()
        self.deathCount = deathCount
        self.deathProximity = deathProximity
        self.deathProximitySum = sum(deathProximity)
        self.dyingUnits = [e.unit for e in events]
        
    
    def __str__(self):
        return f"{self.second} : {self.deathCount} : {self.deathProximitySum} : {self.dyingUnits }"
        
    

