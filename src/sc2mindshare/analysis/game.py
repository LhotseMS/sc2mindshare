from sc2mindshare.reader.compat import ControlGroupKind, control_group_kind, object_text
from sc2mindshare.reader.fork_api import Unit
from sc2mindshare.reader.fork_api import ControlGroupEvent, SelectionEvent, StealControlGroupEvent
from sc2mindshare.analysis.utils import PlayerHandler, MsUtils
from sc2mindshare.reader.fork_api import Replay
import sc2mindshare.analysis.detectors.detectors

from collections import OrderedDict

from sc2mindshare.analysis.text import colored


#TODO remove units first needs a list of units with IDs
#TODO count up units 
# TODO remove steals
class ControlGroup():
    def __init__(self, cge : ControlGroupEvent, units : list, fixes=frozenset()) -> None:
        
        self.fixes = fixes  # CR-080: CG1 switches the game's meaning of set, add and steal (addUnits, removeUnits)
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
        if "CG1" not in self.fixes:
            self.unitsHistory[cge.second] = self.getLatestUnits() + newUnits
            return
        # CR-080 CG1 (Stefan's D1a, D1b, Q-2): set and steal-and-set make the group exactly the selection; add and
        # steal-and-add put the selected units beside the ones it holds. A unit is in a group once (by its id), and
        # every write is a new list (the selection can be another group's live list). A selection that can't be
        # read changes nothing.
        if newUnits is None:
            return
        selected = uniqueUnits(newUnits)
        if control_group_kind(cge) in (ControlGroupKind.SET, ControlGroupKind.STEAL):
            self.unitsHistory[cge.second] = selected
        else:
            held = self.getLatestUnits()
            ids = {u.id for u in held}
            self.unitsHistory[cge.second] = list(held) + [u for u in selected if u.id not in ids]

    def removeUnits(self, second, unitIds):
        """CR-080 CG1 (Stefan's D1b): a steal takes these units out of this group. A new list at ``second`` when the
        group lists one of them; an emptied group stays, holding no units."""
        held = self.getLatestUnits()
        if any(u.id in unitIds for u in held):
            self.unitsHistory[second] = [u for u in held if u.id not in unitIds]

    #TODO use this case
    def unitsStolen(self, scge : StealControlGroupEvent, se : SelectionEvent):
        remainingUnits = list()

        for unit in self.unitsHistory[max(self.unitsHistory)]:
            if unit not in se.new_units:
                remainingUnits.append(unit)

        self.unitsHistory[scge.second] = remainingUnits

    def __str__(self) -> str:
        str = colored("{} {}, Units: {}".format(self.cg_no, object_text(self.player),self.getUnitsStr(second=200)), "blue")
        
        #for sec, units in self.unitsHistory.items():
        #    str += "\n {}: {}".format(sec, units)

        return str

def uniqueUnits(units):
    """CR-080 CG1: each unit once, by its id, the first occurrence kept, in a new list."""
    seen = set()
    out = []
    for u in units:
        if u.id not in seen:
            seen.add(u.id)
            out.append(u)
    return out

class unitAction:
    
    def __init__(self, se, units) -> None:
        
        self.se = se
        self.units = units
        
        pass