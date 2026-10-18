from sc2reader.data import Unit
from sc2reader.events.game import ControlGroupEvent, SelectionEvent, StealControlGroupEvent
from sc2reader.mindshare.utils import PlayerHandler, MsUtils
from sc2reader.resources import Replay
import sc2reader.mindshare.detectors.detectors

from collections import OrderedDict

from termcolor import colored


#TODO remove units first needs a list of units with IDs
#TODO count up units 
# TODO remove steals
class ControlGroup():
    def __init__(self, cge : ControlGroupEvent, units : list) -> None:
        
        self.cg_no = cge.control_group
        self.pid = cge.pid
        self.player = cge.playerName
        
        self.no = cge.control_group

        self.aliveUnitsByType = None
        
        self.unitsHistory = OrderedDict()
        self.location = ()

        self.addUnits(cge, units)
        
        pass
    
    def getLatestUnits(self):
        if len(self.unitsHistory) == 0:
            return list()
        else:
            return next(reversed(self.unitsHistory.values()))
    
    #TODO group units by type, create new class unitManager who is responsible for working with and providing units
    # TODO change how this gets calculated use the part when discarding dead units. 
    def getUnitsStr(self, second):
        return ""
        """self.aliveUnitsByType = {}

        seen = set()
        allAddedUnits = list()
        for key, value in self.unitsHistory.items():
            if key > second:
                break

            for unit in value:
                if unit not in seen:
                    seen.add(unit)
                    allAddedUnits.append(unit)

        aliveUnits = list()
        for unit in allAddedUnits:
            das = unit.diedAtSec
            if das == None or das > second:
                aliveUnits.append(unit) #this is currently unused but a different format to enamurate units and not only type

                MsUtils.iterateType(self.aliveUnitsByType, str(unit))
            
        unitsByType = ""
        for key, value in self.aliveUnitsByType.items():
            unitsByType += "{}".format(str(key)) + str("({})".format(str(value)) if value > 1 else "") + ", "

        return unitsByType"""
                
    def addUnits(self, cge : ControlGroupEvent, newUnits):
        self.unitsHistory[cge.second] = self.getLatestUnits() + newUnits

    #TODO use this case
    def unitsStolen(self, scge : StealControlGroupEvent, se : SelectionEvent):
        remainingUnits = list()

        for unit in self.unitsHistory[max(self.unitsHistory)]:
            if unit not in se.new_units:
                remainingUnits.append(unit)

        self.unitsHistory[scge.second] = remainingUnits

    def __str__(self) -> str:
        str = colored("{} {}, Units: {}".format(self.cg_no, self.player,self.getUnitsStr(second=200)), "blue")
        
        #for sec, units in self.unitsHistory.items():
        #    str += "\n {}: {}".format(sec, units)

        return str

class unitAction:
    
    def __init__(self, se, units) -> None:
        
        self.se = se
        self.units = units
        
        pass