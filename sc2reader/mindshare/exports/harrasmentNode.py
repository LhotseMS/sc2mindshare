from datetime import datetime
from sc2reader.mindshare.exports.node import MultiNode
from sc2reader.mindshare.utils import MsUtils

class HarrasmentNode(MultiNode):
    
    def __init__(self, deathEvents, pullEvent, base, seq):
        super().__init__(deathEvents, deathEvents[0].time, seq)

        self.diedBeforePull = 0
        self.pullDelay = None
        
        self.base = base
        self.pull = pullEvent
        self.events = deathEvents
        self.end = deathEvents[-1].time
        self.totalDeaths = len(deathEvents)

        if pullEvent != None:
            for event in deathEvents:
                if event.time <= pullEvent.time:
                    self.diedBeforePull += 1
                    
            self.pullDelay = MsUtils.intervalBetween(self.event.time, pullEvent.time)
            self.afterPull = self.totalDeaths - self.diedBeforePull

        
        self.type = "Harrasment"
        self.propertiesCount = 6
            
    def getNodeName(self):
        if self.pull == None:
            return "{} died, no pull".format(self.totalDeaths)
        else:
            return "{} dief, before pull".format(self.totalDeaths)
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        str = "{} workers died at {} from {} to {}.".format(self.totalDeaths, self.base, self.startTime, self.end)
        
        if self.pull != None:
            str += "\nPull occured after {}s with {} workers dead.".format(self.pullDelay, self.diedBeforePull)
    
    def getProperties(self, sep):
        return "{}{}{}{}{}".format(super().getProperties(sep),
                               self.end, sep,
                               self.totalDeaths, sep,
                               self.pullDelay, sep,
                               self.diedBeforePull, sep)
        