from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.events.tracker import UnitDoneEvent
from sc2reader.mindshare.utils import MsUtils

#TODO add building deaths. Unit killed them. Tied to battle? Was that unit in battle? 
class BuildingNode(SimpleNode):

    def __init__(self, e : UnitDoneEvent, buildTime, seq) -> None:
        super().__init__(e, seq)

        self.subtype = self.event.replaceStrings(self.event.unit, False).strip()

        self.event.unit.unitsNode = self
        self.buildTime = int(buildTime)

        self.propertiesCount = 3
        self.type = "Building"
        self.index = None

    # TODO get a clean name withou race in ()
    def getNodeName(self):

        if self.event.unit.baseName != None:
            nameStr = self.event.replaceStrings(self.event.unit.baseName, True).strip()
        else:
            nameStr = self.event.replaceStrings(self.event.unit, True).strip()

        if self.index != None and self.index > 0:
            nameStr += " " + str(self.index)

        return nameStr
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return ""
    
    def getProperties(self, sep):
        return "{}{}{}".format(super().getProperties(sep),
                               self.subtype, sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return MsUtils.decrementSeconds("00:" + self.event._str_prefix().replace(".",":").strip(), self.buildTime)
    
    
