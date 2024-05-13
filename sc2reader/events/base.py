import re

class Event:
    name = "Event"

    def isUnique(self, prevEvent):
        return True
        
    def isPlayer(self, pids):
        return False
    
    
    # modify data for JSON a bit
    def replaceStrings(self , input, split=False):
        replacements = {
            "Player 1 - ": "",
            "Player 2 - ": "",
            " (Terran)": "",
            " (Zerg)": "",
            " upgrade completed": ""
        }

        source_string = str(input)

        for old, new in replacements.items():
            source_string = source_string.replace(old, new)
        
        source_string = re.sub(r"\[\w+\]", "", source_string)

        # split by capital letters
        if split:
            source_string = re.sub(r'(?<=[a-z])([A-Z0-9])|^[A-Z]', lambda match: (' ' if match.start() != 0 else '') + match.group(0), source_string)

        return source_string
    
    
