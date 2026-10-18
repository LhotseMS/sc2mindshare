from datetime import datetime
from sc2reader.mindshare.exports.node import Node, X_LD
from sc2reader.mindshare.utils import MsUtils

class ScoutNode(Node):
    
    
    #TODO which player scouted who
    #TODO links to buildings that have been scouted
    
    def __init__(self, unit, time, scoutedBase, scoutedBuildings, seq):
        super().__init__(seq)

        self.player = unit.player
        self.unit = unit
        self.scoutedBase = scoutedBase
        self.scoutedBuildings = scoutedBuildings

        self.time = time

        self.type = "Scouting"
        self.propertiesCount = 4
            
    def getNodeName(self):
        return "{} scouted {}".format(self.unit.name, self.scoutedBase)
    
    def getNodeDescription(self):
        str = "At {} the following was scouted:".format(self.time, X_LD)

        for building in self.scoutedBuildings:
            str += "   {}{}".format(building.name, X_LD)

        return str
    
    def getProperties(self, sep):
        return "{}{}{}{}{}".format(super().getProperties(sep),
                               self.unit.name, sep,
                               self.scoutedBase, sep)
        
    def getNodePlayer(self):
        return MsUtils.replaceStrings(self.player)
    
    def getNodeTime(self):
        return self.time.replace(".",":").strip()