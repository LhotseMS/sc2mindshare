from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.events.message import ChatEvent


class ChatNode(SimpleNode):
    
    def __init__(self, e : ChatEvent, seq) -> None:
        super().__init__(e, seq)

        # TODO change pid to player name
        self.player = e.pid
        self.text = e.text

        self.propertiesCount = 2
        self.type = "Chat"

    def getNodeName(self):
        return "{}".format(self.text)

    def getNodeDescription(self):
        return "{}:{}".format(self.pid, self.text)
    
    def getProperties(self, sep):
        return "{}".format(super().getProperties(sep))
    
    def getNodePlayer(self) -> str: 
        return self.pid

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()