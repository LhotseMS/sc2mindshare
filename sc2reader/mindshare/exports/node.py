# line delimiter as csv doesn't like \n. Replaced back in excel
X_LD = "X_LD"

class Exportable:   
    
    propertiesCount = None

# TODO rename all functions and remove "node"
class Node(Exportable):

    def __init__(self, seq) -> None:
        
        self.seq = seq
        self.id = None
        self.type = None

    def getNodeName(self) -> str: pass
    def getNodeDescription(self) -> str: pass
    def getProperties(self, separator) -> str:
        return (self.getNodeTime() + separator + 
               self.getNodePlayer() + separator)

    def getNodeType(self) -> str: 
        return self.type
    
    def getNodeID(self) -> str:
        if self.id == None:
            self.id = self.getNodeIDBase() + str(self.seq)
        return self.id

    def getNodeIDBase(self) -> str:
        return self.getNodeType() + "-"
    
    def getNodeLinks(self) -> str: pass
    def getNodeTime(self) -> str: pass
    def getNodeImages(self) -> str: 
        return ""
    
    def getNodePlayer(self) -> str:
        return self.event.replaceStrings(self.event.player)
    

class SimpleNode(Node):

    def __init__(self, e, seq) -> None:
        super().__init__(seq)

        self.event = e
        self.type = None

    def getNodeName(self) -> str: pass
    def getNodeDescription(self) -> str: pass
    def getProperties(self, separator) -> str: return super().getProperties(separator)
    def getNodeType(self) -> str:  return super().getNodeType()
    def getNodeIDBase(self) -> str:  return super().getNodeIDBase()
    def getNodeLinks(self) -> str: pass
    def getNodeTime(self) -> str: pass
    def getNodePlayer(self) -> str: return super().getNodePlayer()

        
# multi event node
class MultiNode(Node):

    def __init__(self, es, startTime, seq) -> None:
        super().__init__(seq)

        self.events = es
        self.event = es[0]
        self.startTime = startTime
        self.count = self.events.__len__()

        # TODO unit or the event should provide the cleaned name, #
        self.name = self.event.unit.nameC
        
    def getNodeName(self) -> str: 
        if self.count > 1:
            return "{} {}s".format(self.count, self.name)
        else:
            return "{}".format(self.name)

    def getNodeDescription(self):
        if self.count > 1:
            return "{} {}s completed by {} in last 10s from {}".format(self.count, self.name, self.getNodePlayer(), self.startTime)
        else:
            return "{} completed by {} in last 10s from {}".format(self.name, self.getNodePlayer(), self.startTime)
    
    def getProperties(self, separator) -> str: return super().getProperties(separator)
    def getNodeType(self) -> str:  return super().getNodeType()
    def getNodeIDBase(self) -> str:  return super().getNodeIDBase()
    def getNodeLinks(self) -> str: pass
    def getNodeTime(self) -> str: 
        return self.startTime
    
    def getNodePlayer(self):
        return self.event.replaceStrings(self.event.player)
