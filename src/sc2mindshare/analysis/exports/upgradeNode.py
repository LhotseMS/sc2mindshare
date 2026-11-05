from sc2mindshare.reader.compat import clean_name
import re

from sc2mindshare.analysis.exports.node import SimpleNode
from sc2mindshare.reader.fork_api import UpgradeCompleteEvent
from sc2mindshare.analysis.utils import MsUtils


class UpgradeNode(SimpleNode):
    
    LEVELS_PATTERN = r'Level \d+$'

    def __init__(self, e : UpgradeCompleteEvent, upgradeTime, seq, *, fixes) -> None:
        super().__init__(e, seq, fixes=fixes)

        name = self.getNodeName()
        self.subtype = re.sub(self.LEVELS_PATTERN, '', name).strip()
        if "Level" in name:     
            self.level = name[-1]
        else:
            self.level = None      

        if "Weapons" in name:
            self.interaction = "Offence"
        elif "Armors" in name:
            self.interaction = "Defence"
        else:
            self.interaction = None

        self.upgradeTime = int(upgradeTime)

        self.propertiesCount = 3
        self.type = "Upgrade"

    def getNodeName(self):
        return "{}".format(clean_name(self.event.upgrade_type_name, True, self.fixes).strip())

    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return "{} completed {} at {}".format(self.getNodePlayer(),
                           self.getNodeName(),
                           self.getNodeTime())
    
    def getProperties(self, sep):
        return "{}".format(super().getProperties(sep),
                           self.subtype, sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return MsUtils.decrementSeconds("00:" + self.event._str_prefix().replace(".",":").strip(), self.upgradeTime)
    
