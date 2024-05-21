from data import Unit
from events.game import ControlGroupEvent, SelectionEvent, StealControlGroupEvent
from resources import Replay

from termcolor import colored


#TODO remove units first needs a list of units with IDs
#TODO count up units 
# TODO remove steals
class ControlGroup:
    def __init__(self, se : SelectionEvent, ce : ControlGroupEvent) -> None:
        
        self.cg_no = ce.control_group
        self.pid = ce.pid
        self.player = se.playerName
        
        self.no = ce.control_group
        
        self.unitsHistory = {}
        self.location = ()

        self.addUnits(se)
        
        pass
    
    #TODO just omit the units that have already died
    @property
    def getUnits(self, second):
        units = None
        for key, value in self.unitsHistory.items():
            if key > second:
                break            
            units = value
        
        aliveUnits = list()
        for unit in units:
            das = unit.diedAtSec()
            if das != None and das > second:
                aliveUnits.append(unit)
            
        return aliveUnits
            
    def update(self, se : SelectionEvent):
        self.addUnits(se)
        pass
    
    def addUnits(self, cge : ControlGroupEvent, se : SelectionEvent):
        self.unitsHistory[cge.second] = se.new_units

    def unitsStolen(self, scge : StealControlGroupEvent, se : SelectionEvent):
        remainingUnits = list()

        for unit in self.unitsHistory[max(self.unitsHistory)]:
            if unit not in se.new_units:
                remainingUnits.append(unit)

        self.unitsHistory[scge.second] = remainingUnits

    def __str__(self) -> str:
        str = colored("{} {}".format(self.cg_no, self.player), "blue")
        
        for sec, units in self.unitsHistory.items():
            str += "\n {}: {}".format(sec, units)

        return str

class unitAction:
    
    def __init__(self, se, units) -> None:
        
        self.se = se
        self.units = units
        
        pass