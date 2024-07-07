import re

from datetime import datetime, timedelta


# change this to util class and just reference it instead of inheriting an util renamer
class Renamer:

     
    # modify data for JSON a bit
    def replaceStrings(self , input, split=False):
        replacements = {
            "Player 1 - ": "",
            "Player 2 - ": "",
            " (Terran)": "",
            " (Zerg)": "",
            " (Protoss)": "",   
            " upgrade completed": "",
            "Attack": "A-move", 
            "zerglingmovementspeed": "Zergling Movement Speed",
            "zerglingattackpeed": "Zergling Attack Speed"
        }

        source_string = str(input)

        for old, new in replacements.items():
            source_string = source_string.replace(old, new)
        
        source_string = re.sub(r"\[\w+\]", "", source_string)

        # split by capital letters
        if split:
            source_string = re.sub(r'(?<=[a-z])([A-Z0-9])|^[A-Z]', lambda match: (' ' if match.start() != 0 else '') + match.group(0), source_string)

        return source_string.rstrip()
    

class MsUtils:
    
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

        
    def incrementSeconds(time_string: str, seconds) -> str:
        # Parse the time string into a datetime object
        time_obj = datetime.strptime(time_string, "%H:%M:%S")
        # Increment the seconds by 1
        time_obj += timedelta(seconds=seconds)
        # Convert the datetime object back to a string
        incremented_time_string = time_obj.strftime("%H:%M:%S")
        return incremented_time_string

    
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