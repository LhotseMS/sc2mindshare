from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.events.message import MessageEvent


class MessageNode(SimpleNode):
    
    def __init__(self, e : MessageEvent) -> None:
        super().__init__(e)

        self.propertiesCount = 1
        self.type = "Message"

    def getNodeName(self):
        return "{}".format(self.event.replaceStrings(self.event.text, True).strip())

    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return "{} {}: {} ".format(self.getNodeTime(),
                           self.getNodePlayer(),
                           self.event.text)
    
    def getProperties(self, sep):
        return "{}".format(super().getProperties(sep))
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()