from sc2mindshare.reader.compat import clean_name
from datetime import datetime
from sc2mindshare.analysis.exports.node import Node, X_LD
from sc2mindshare.analysis.utils import MsUtils

class ScoutNode(Node):
    
    
    #TODO which player scouted who
    #TODO links to buildings that have been scouted
    
    def __init__(self, unit, time, scoutedBase, scoutedBuildings, seq, *, fixes):
        super().__init__(seq, fixes=fixes)

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
        return clean_name(self.player, False, self.fixes)
    
    def getNodeTime(self):
        return self.time.replace(".",":").strip()