from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.events.tracker import UpgradeCompleteEvent


class UpgradeNode(SimpleNode):
    
    def __init__(self, e : UpgradeCompleteEvent, seq) -> None:
        super().__init__(e, seq)

        self.propertiesCount = 2
        self.type = "Upgrade"

    def getNodeName(self):
        return "{}".format(self.event.replaceStrings(self.event.upgrade_type_name, True).strip())

    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return "{} completed {} at {}".format(self.getNodePlayer(),
                           self.getNodeName(),
                           self.getNodeTime())
    
    def getProperties(self, sep):
        return "{}".format(super().getProperties(sep))
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()
    
