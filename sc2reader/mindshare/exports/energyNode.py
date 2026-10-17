from datetime import datetime
from sc2reader.mindshare.exports.node import Node
from sc2reader.mindshare.utils import MsUtils

class EnergyNode(Node):
    
    def __init__(self, unit, excessStart, curTime, curEnergy, excessThreshold, seq):
        super().__init__(seq)

        self.player = unit.player
        self.unitName = unit.name
        self.unitID = unit.id
        self.start = "00:" + excessStart.replace(".",":")
        self.end = None
        self.energy = curEnergy
        self.timeDetected = curTime
        self.threshold = excessThreshold

        self.duration = None

        self.type = "Energy Excess"
        self.propertiesCount = 6
    
    def setEnd(self, endTime):
        self.end = "00:" + endTime.replace(".",":")

        end = datetime.strptime(self.end, '%H:%M:%S')
        start = datetime.strptime(self.start, '%H:%M:%S')

        self.duration = int((end - start).total_seconds())
        
    def getNodeName(self):
        return "{} over {} energy".format(self.unitName, self.threshold)
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return "{} has excess energy over {} for {}s from {} to {}".format(self.unitName, self.threshold, self.duration, self.start, self.end)
    
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

    def __str__(self) -> str:
        return "{} : {}({}) {}-{} {} {} {}".format(self.player, self.unitName, self.unitID, self.start, self.end, self.duration, self.energy, self.timeDetected)