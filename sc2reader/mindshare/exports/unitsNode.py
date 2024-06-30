from sc2reader.mindshare.exports.node import MultiNode
from sc2reader.events.tracker import UnitDoneEvent, UnitBornEvent, TrackerEvent

class UnitsNode(MultiNode):

    def __init__(self, es : list, st, seq) -> None:
        super().__init__(es, st, seq)

        self.supply = 0

        for e in self.events:
            self.supply += e.unit.supply

        self.type = "Units"
        self.propertiesCount = 4
        self.currentUnits = 0
    
    def getProperties(self, sep):
        return "{}{}{}{}{}{}{}{}{}".format(super().getProperties(sep),
                             self.name, sep,
                             self.count, sep,
                             self.supply, sep,
                             self.currentUnits, sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def setCurrenCount(self, cc):
        self.currentUnits = cc