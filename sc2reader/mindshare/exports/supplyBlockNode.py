from datetime import datetime
from sc2reader.mindshare.exports.node import Node
from sc2reader.mindshare.utils import MsUtils

class SupplyBlockNode(Node):
    
    def __init__(self, player, blockStart, blockEnd, seq):
        super().__init__(seq)

        self.player = player
        self.start = "00:" + blockStart
        self.end = "00:" + blockEnd

        end = datetime.strptime(self.end, '%H:%M:%S')
        start = datetime.strptime(self.start, '%H:%M:%S')

        self.duration = int((end - start).total_seconds())

        self.type = "Supply Block"
        self.propertiesCount = 4
    
    def getNodeName(self):
        return "{}s Supply Block".format(self.duration)
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return "Supply block started at {} and ended at {} for a duration of {}s".format(self.start, self.end, self.duration)
    
    def getProperties(self, sep):
        return "{}{}{}{}{}".format(super().getProperties(sep),
                               self.end, sep,
                               self.duration, sep)
        
    def getNodePlayer(self):
        return MsUtils.replaceStrings(self.player)
    
    def getNodeTime(self):
        return self.start.replace(".",":").strip()