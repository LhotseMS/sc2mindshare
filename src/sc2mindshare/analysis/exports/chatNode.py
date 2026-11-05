from sc2mindshare.analysis.exports.node import SimpleNode
from sc2mindshare.reader.compat import object_text
from sc2mindshare.reader.fork_api import ChatEvent


class ChatNode(SimpleNode):
    
    def __init__(self, e : ChatEvent, seq, player, *, fixes) -> None:
        super().__init__(e, seq, fixes=fixes)

        # TODO change pid to player name
        self.player = player
        self.text = e.text

        self.propertiesCount = 2
        self.type = "Chat"

    def getNodeName(self):
        return "{}".format(self.text).replace(";",":")

    def getNodeDescription(self):
        return "{}: {}".format(object_text(self.player, self.fixes), self.text).replace(";",":")
    
    def getProperties(self, sep):
        return "{}".format(super().getProperties(sep))
    
    def getNodePlayer(self) -> str: 
        return self.player

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()