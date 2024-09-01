import re
import math

from datetime import datetime, timedelta


# change this to util class and just reference it instead of inheriting an util renamer
class Renamer:

     
    # modify data for JSON a bit
    def replaceStrings(self , input, split=False):
        return MsUtils.replaceStrings(input, split)
    

class MsUtils:
    
    def replaceStrings(input, split=False):
        replacements = {
            "Player 1 - ": "",
            "Player 2 - ": "",
            " (Terran)": "",
            " (Zerg)": "",
            " (Protoss)": "",   
            " upgrade completed": "",
            "Attack": "A move", 
            "zerglingmovementspeed": "ZerglingMovementSpeed",
            "zerglingattackspeed": "ZerglingAttackSpeed",
            "Chrono Boost Energy Cost" : "Chrono Boost",
            "Spawn larva" : "Inject",
            "SiegeTankSieged" : "Sieged Tank",
            "Terran": "",
            "Zerg": ""
        }

        source_string = str(input)

        for old, new in replacements.items():
            source_string = source_string.replace(old, new)
        
        source_string = re.sub(r"\[\w+\]", "", source_string)

        # split by capital letters
        if split:
            source_string = re.sub(r'(?<=[a-z])([A-Z0-9])|^[A-Z]', lambda match: (' ' if match.start() != 0 else '') + match.group(0), source_string)

        return source_string.rstrip()

    def calculateY1(x2, y1, y2, alpha):
        
        angle_a_radians = math.radians(alpha)
        delta_y = y2 - y1

        return x2 - (delta_y / math.tan(angle_a_radians))

    # TODO utility?
    def iterateType(typedDict, type):
        if not type in typedDict:
            typedDict[type] = 1
        else:
            typedDict[type] = typedDict[type] + 1
    
    #TODO this should work on minutes and hours
    def isLater(firstTime, laterTime) -> bool:
        ft = datetime.strptime(firstTime, "%M:%S")
        lt = datetime.strptime(laterTime, "%M:%S")

        return lt > ft

    def intervalBetween(firstTime, laterTime) -> float:
        ft = datetime.strptime(firstTime.replace(".",":"), "%M:%S")
        lt = datetime.strptime(laterTime.replace(".",":"), "%M:%S")

        return (lt - ft).total_seconds()
        
    def decrementSeconds(time_string: str, seconds) -> str:
        time_obj = datetime.strptime(time_string, "%H:%M:%S")
        time_obj -= timedelta(seconds=seconds)
        incremented_time_string = time_obj.strftime("%H:%M:%S")
        return incremented_time_string
        
    def incrementSeconds(time_string: str, seconds) -> str:
        time_obj = datetime.strptime(time_string, "%H:%M:%S")
        time_obj += timedelta(seconds=seconds)
        incremented_time_string = time_obj.strftime("%H:%M:%S")
        return incremented_time_string

    def timeToSeconds(time_str):
        minutes, seconds = map(int, time_str.split('.'))
        total_seconds = minutes * 60 + seconds
        return total_seconds
    
class PlayerHandler:
    
    # TODO move to util class    
    def initDictByPlayer(self, type = 1):
        d = {}

        if type == 0:
            d[self.player1] = 0 
            d[self.player2] = 0
        elif type == 1:
            d[self.player1] = list()
            d[self.player2] = list()
        elif type == 2:
            d[self.player1] = {}
            d[self.player2] = {}

        return d