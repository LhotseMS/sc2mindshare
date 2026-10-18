from sc2mindshare.analysis.exports.buildingNode import BuildingNode
from sc2mindshare.reader.compat import clean_name, object_text
from sc2mindshare.reader.fork_api import UnitInitEvent


#TODO add building deaths. Unit killed them. Tied to battle? Was that unit in battle? 
class InitNode(BuildingNode):

    def __init__(self, e : UnitInitEvent, seq, *, fixes) -> None:
        super().__init__(e, 0, seq, fixes=fixes)

        self.subtype = clean_name(self.event.unit, False, self.fixes).strip()

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
        nameStr = clean_name(self.event.unit, True, self.fixes).strip()

        if self.index != None and self.index > 0:
            nameStr += " " + str(self.index)

        return nameStr
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        if self.cancelled:
            return "{} started building at {} but was cancelled".format(object_text(self.event.unit, self.fixes), self.getNodeTime())
        else:
            return "{} started building at {} but was killed".format(object_text(self.event.unit, self.fixes), self.getNodeTime())
    
    def getProperties(self, sep):
        return "{}{}{}".format(super().getProperties(sep),
                               self.subtype, sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()
    
    
