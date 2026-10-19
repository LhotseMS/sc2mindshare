from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.events.message import ChatEvent


class ChatNode(SimpleNode):
    
    def __init__(self, e : ChatEvent, seq, player) -> None:
        super().__init__(e, seq)

        # TODO change pid to player name
        self.player = player
        self.text = e.text

        self.propertiesCount = 2
        self.type = "Chat"

    def getNodeName(self):
        return "{}".format(self.text).replace(";",":")

    def getNodeDescription(self):
        return "{}: {}".format(self.player, self.text).replace(";",":")
    
    def getProperties(self, sep):
        return "{}".format(super().getProperties(sep))
    
    def getNodePlayer(self) -> str: 
        return self.player

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()