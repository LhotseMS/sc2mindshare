from datetime import datetime, timedelta
from sc2reader.mindshare.exports.node import SimpleNode

# TODO this should probably be a supertype of Node that doesn't have time etc. now its just ommitted
class GameNode(SimpleNode): 

    def __init__(self, replay) -> None:
        self.map = replay.map_name
        # TODO get map image and heatmap for deaths and buildings

        if replay.players[0].result == "Win":
            self.winningPlayer = replay.players[0].name
        else:
            self.winningPlayer = replay.players[1].name

        if replay.time_zone == 0:
            self.timeZone = "UTC"
        elif replay.time_zone > 0:
            self.timeZone = "UTC+".format(replay.time_zone)
        else:
            self.timeZone = "UTC".format(replay.time_zone)

        self.datePlayed = replay.date
        self.duration = datetime.strptime(replay.length, "%H:%M:%S")

        self.speed = replay.speed
        self.ladder = replay.is_ladder
        self.type = replay.type
        self.category = replay.category

        self.type = "Game"
        self.propertiesCount = 7

    def getNodeName(self):

        if self.ladder:
            nameStr = "Ladder"
        else:
            nameStr = self.category

        nameStr += self.map
        
        return nameStr
        
    def getNodeDescription(self):
        return "Played on {} {}, for {}.\n Won by {}".format(self.datePlayed, self.duration, self.timeZone, self.winningPlayer)
    
    def getProperties(self, sep):
        return "{}{}{}{}{}{}{}{}{}{}{}{}{}{}".format(self.speed, sep,
                               self.ladder, sep,
                               self.type, sep,
                               self.category, sep,
                               self.duration, sep,
                               self.datePlayed, sep,
                               self.timeZone, sep)
    
