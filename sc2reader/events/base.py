from mindshare.utils import Renamer

class Event(Renamer):
    name = "Event"

    def isUnique(self, prevEvent):
        return True
        
    def isPlayer(self, pids):
        return False
    
       
    
