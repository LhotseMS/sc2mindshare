from datetime import datetime
from sc2reader.mindshare.exports.node import Node
from sc2reader.mindshare.utils import MsUtils

class InjecDelayNode(Node):
    
    def __init__(self, unit, start, end, duration, delayThreshold, seq):
        super().__init__(seq)

        self.player = unit.player
        self.unitName = unit.name
        self.unitID = unit.id
        self.start = "00:" + start.replace(".",":")
        self.end = "00:" + end.replace(".",":")
        self.threshold = delayThreshold

        self.duration = duration.total_seconds()

        self.type = "Inject Delay"
        self.propertiesCount = 6
            
    def getNodeName(self):
        return "{}s No Injects".format(self.duration)
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return "{} didn't get injects for {}s from {} to {}".format(self.unitName, self.duration, self.start, self.end)
    
    def getProperties(self, sep):
        return "{}{}{}{}{}".format(super().getProperties(sep),
                               self.end, sep,
                               self.duration, sep,
                               self.threshold, sep,
                               self.unitName, sep)
        
    def getNodePlayer(self):
        return MsUtils.replaceStrings(self.player)
    
    def getNodeTime(self):
        return self.start.replace(".",":").strip()