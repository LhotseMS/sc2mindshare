from datetime import datetime, timedelta
from sc2mindshare.analysis.exports.node import SimpleNode, X_LD
from sc2mindshare.analysis.offline import ImageUploader

def utc_offset(hours):
    """CR-023 P9: ``UTC-5``, ``UTC+1``, ``UTC+5:30``; ``UTC`` for no offset."""
    if not hours:
        return "UTC"
    sign = "+" if hours > 0 else "-"
    minutes = round(abs(hours) * 60)
    return f"UTC{sign}{minutes // 60}" + (f":{minutes % 60:02d}" if minutes % 60 else "")


# TODO this should probably be a supertype of Node that doesn't have time etc. now its just ommitted
class GameNode(SimpleNode): 

    def __init__(self, replay, heatMapID, *, fixes) -> None:
        self.fixes = fixes
        self.id = None
        self.seq = 1
        self.images = list()

        self.map = replay.map_name
        # TODO get map image and heatmap for deaths and buildings

        if replay.players[0].result == "Win":
            self.winningPlayer = replay.players[0].name
        else:
            self.winningPlayer = replay.players[1].name

        if "P9" in self.fixes:  # CR-023 P9 (D17a): the recording PC's offset; the date itself is UTC
            self.timeZone = utc_offset(replay.time_zone)
        elif replay.time_zone == 0:
            self.timeZone = "UTC"
        elif replay.time_zone > 0:
            self.timeZone = "UTC+".format(replay.time_zone)
        else:
            self.timeZone = "UTC".format(replay.time_zone)

        self.datePlayed = replay.date
        # TODO change format 
        self.duration = datetime.strptime(str(replay.length), "%M.%S").strftime("%H:%M:%S")

        self.speed = replay.speed
        self.ladder = replay.is_ladder
        self.type = replay.type
        self.category = replay.category

        self.addImage("{}{}".format(ImageUploader.RESOURCE_URL, heatMapID))

        self.type = "Game"
        self.propertiesCount = 7

    def getNodeName(self):

        if self.ladder:
            nameStr = "Ladder"
        else:
            nameStr = self.category

        nameStr += " {}".format(self.map)
        
        return nameStr
        
    def getNodeDescription(self):
        zone = "UTC" if "P9" in self.fixes else self.timeZone  # CR-023 P9: replay.date is UTC
        return "Played on {} {} for {}.{}The game was won by {}".format(self.datePlayed, zone, self.duration, X_LD, self.winningPlayer)
    
    def getProperties(self, sep):
        return "{}{}{}{}{}{}{}{}{}{}{}{}{}{}".format(self.speed, sep,
                               self.ladder, sep,
                               self.type, sep,
                               self.category, sep,
                               self.duration, sep,
                               self.datePlayed, sep,
                               self.timeZone, sep)
    
    
    
