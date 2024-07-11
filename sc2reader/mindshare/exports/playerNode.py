from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.objects import Player

class PlayerNode(SimpleNode): 
    
    def __init__(self, player : Player) -> None:

        # TODO map region numbers to descriptions
        self.region = player.region
        self.subregion = player.subregion

        self.name = player.name
        self.race = player.race
        self.color = player.color

        self.builtUnits = len(player.units)
        self.killedUnits = len(player.killed_units)

        self.type = "Player"
        self.propertiesCount = 4
    
    def getNodeName(self):
        return self.name
        
    def getNodeDescription(self):
        return "{} {} build {} units and killed {} units.".format(self.color, self.race, self.builtUnits, self.killedUnits)
    
    def getProperties(self, sep):
        return "{}{}{}{}{}{}{}{}".format(self.name, sep,
                         self.race, sep,
                         self.region, sep,
                         self.subregion, sep)