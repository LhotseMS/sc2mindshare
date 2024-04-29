from data import Unit
from events.game import ControlGroupEvent, SelectionEvent
from resources import Replay


class ControlGroup:
    def __init__(self, se : SelectionEvent, ce : ControlGroupEvent) -> None:
        
        self.cg_no = ce.control_group
        self.pid = ""
        self.player = se.playerName
        
        self.no = ce.control_group
        
        self.unitsHistory = list()
        self.addUnits(se)
        self.location = ()
        
        pass
    
    @property
    def currentUnits(self):
        return self.unitsHistory[self.unitsHistory.count-1]
            
    def update(self, se : SelectionEvent):
        self.addUnits(se)
        pass
    
    def addUnits(self, se : SelectionEvent):
        self.unitsHistory.append((se.frame ,se.new_units))

class unitAction:
    
    def __init__(self, se, units) -> None:
        
        self.se = se
        self.units = units
        
        pass