from sc2mindshare.reader.compat import clean_name, supply_at, type_at
from sc2mindshare.analysis.exports.node import MultiNode
from sc2mindshare.reader.fork_api import UnitDoneEvent, UnitBornEvent, TrackerEvent

class UnitsNode(MultiNode):

    def __init__(self, es : list, st, seq, *, fixes) -> None:
        super().__init__(es, st, seq, fixes=fixes)

        self.supply = 0

        for e in self.events:
            # CR-023 S6 (D15a): the supply of the unit's type at its event, not of its final type
            self.supply += supply_at(e.unit, e.frame) if "S6" in self.fixes else e.unit.supply
            e.unit.unitsNode = self

        # TODO unit or the event should provide the cleaned name, #
        # the fork's nameC, with the fixes (P2); by the type at the event under N1 (CR-023, D6a)
        unit_type = type_at(self.event.unit, self.event.frame) if "N1" in self.fixes else self.event.unit.name
        self.name = clean_name(unit_type, True, self.fixes)

        self.type = "Units"
        self.propertiesCount = 4
        self.currentUnits = 0
    
    def getProperties(self, sep):
        return "{}{}{}{}{}{}{}{}{}".format(super().getProperties(sep),
                             self.name, sep,
                             self.count, sep,
                             self.supply, sep,
                             self.currentUnits, sep)
    
    def getNodeDescription(self):
        if self.count > 1:
            return "{} {}s completed by {} in last 10s from {}".format(self.count, self.name, self.getNodePlayer(), self.startTime)
        else:
            return "{} completed by {} in last 10s from {}".format(self.name, self.getNodePlayer(), self.startTime)
        
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def setCurrenCount(self, cc):
        self.currentUnits = cc