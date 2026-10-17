from sc2reader.mindshare.exports.buildingNode import BuildingNode
from sc2reader.events.tracker import UnitInitEvent

#TODO add building deaths. Unit killed them. Tied to battle? Was that unit in battle? 
class InitNode(BuildingNode):

    def __init__(self, e : UnitInitEvent, seq) -> None:
        super().__init__(e, 0, seq)

        self.subtype = self.event.replaceStrings(self.event.unit, False).strip()

        self.event.unit.initNode = self
        if self.event.unit.deathEvent == None:
            self.cancelled = False
        else:
            self.cancelled = self.event.unit.deathEvent.killing_player == self.event.player

        self.propertiesCount = 1
        self.type = "Initiated"
        self.index = None

    # TODO get a clean name withou race in ()
    def getNodeName(self):
        nameStr = self.event.replaceStrings(self.event.unit, True).strip()

        if self.index != None and self.index > 0:
            nameStr += " " + str(self.index)

        return nameStr
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        if self.cancelled:
            return "{} started building at {} but was cancelled".format(self.event.unit, self.getNodeTime())
        else:
            return "{} started building at {} but was killed".format(self.event.unit, self.getNodeTime())
    
    def getProperties(self, sep):
        return "{}{}{}".format(super().getProperties(sep),
                               self.subtype, sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()
    
    
