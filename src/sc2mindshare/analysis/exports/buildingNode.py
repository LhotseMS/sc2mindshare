from sc2mindshare.analysis.exports.node import SimpleNode
from sc2mindshare.reader.fork_api import UnitDoneEvent
from sc2mindshare.analysis.utils import MsUtils
from sc2mindshare.reader.compat import clean_name, unit_text_at

#TODO add building deaths. Unit killed them. Tied to battle? Was that unit in battle? 
class BuildingNode(SimpleNode):

    def __init__(self, e : UnitDoneEvent, buildTime, seq, *, fixes) -> None:
        super().__init__(e, seq, fixes=fixes)

        self.subtype = clean_name(self.unitText(), False, self.fixes).strip()

        self.event.unit.unitsNode = self
        self.buildTime = int(buildTime)

        self.propertiesCount = 3
        self.type = "Building"
        self.index = None

    # TODO get a clean name withou race in ()
    def getNodeName(self):

        if self.event.unit.baseName != None:
            nameStr = clean_name(self.event.unit.baseName, True, self.fixes).strip()
        else:
            nameStr = clean_name(self.unitText(), True, self.fixes).strip()

        if self.index != None and self.index > 0:
            nameStr += " " + str(self.index)

        return nameStr
    
    def unitText(self):
        """The building as text: its type at its event under N1 (CR-023, D6a), else the unit (its final type)."""
        if "N1" in self.fixes:
            return unit_text_at(self.event.unit, self.event.frame, self.fixes)
        return self.event.unit

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
    
    
