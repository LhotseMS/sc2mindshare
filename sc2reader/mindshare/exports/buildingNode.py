from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.events.tracker import UnitDoneEvent

#TODO add building deaths. Unit killed them. Tied to battle? Was that unit in battle? 
class BuildingNode(SimpleNode):

    def __init__(self, e : UnitDoneEvent, seq) -> None:
        super().__init__(e, seq)
        self.propertiesCount = 1
        self.type = "Building"
        self.index = None

    # TODO get a clean name withou race in ()
    def getNodeName(self):
        nameStr = self.event.replaceStrings(self.event.unit, True).strip()

        if self.index != None and self.index > 0:
            nameStr += " " + str(self.index)

        return nameStr
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return ""
    
    def getProperties(self, sep):
        return "{}{}{}".format(super().getProperties(sep),
                             self.event.replaceStrings(self.event.unit, False).strip(), sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()
    
    
