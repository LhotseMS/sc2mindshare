from sc2mindshare.reader.compat import clean_name
from sc2mindshare.analysis.exports.node import MultiNode
from sc2mindshare.reader.fork_api import UnitDoneEvent, UnitBornEvent, TrackerEvent

class UnitsNode(MultiNode):

    def __init__(self, es : list, st, seq, *, fixes) -> None:
        super().__init__(es, st, seq, fixes=fixes)

        self.supply = 0

        for e in self.events:
            self.supply += e.unit.supply
            e.unit.unitsNode = self

        # TODO unit or the event should provide the cleaned name, #
        self.name = clean_name(self.event.unit.name, True, self.fixes)  # the fork's nameC, with the fixes (P2)

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