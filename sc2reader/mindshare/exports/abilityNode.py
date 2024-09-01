from sc2reader.mindshare.exports.node import SimpleNode
from sc2reader.events.game import CommandEvent

#TODO add building deaths. Unit killed them. Tied to battle? Was that unit in battle? 
class AbilityNode(SimpleNode):

    def __init__(self, e : CommandEvent, seq) -> None:
        super().__init__(e, seq)

        self.subtype = self.event.replaceStrings(self.event.ability.name, False).strip()

        self.queued = bool(self.event.flag["queued"])
        self.minimap = bool(self.event.flag["minimap"])
        self.combat = self.event.isCombat()
        self.target = self.event.replaceStrings(self.event.target.name)

        self.propertiesCount = 5
        self.type = "Ability"

    # TODO get a clean name withou race in ()
    def getNodeName(self):
        return self.event.replaceStrings(self.event.ability.name, True).strip()
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        
        desc = ""
        
        if self.combat:
            desc += "Combat ability '{}'".format(self.getNodeName())
        else:
            desc += "Non-combat ability '{}'".format(self.getNodeName())
        
        if self.event.ability_type == "TargetUnit":
            desc += " targetted {}".format(self.event.replaceStrings(self.target))

        if self.queued:
            desc += " queued"

        if self.minimap:
            desc += " on minimap"

        return desc + "."
    
    def getProperties(self, sep):
        return "{}{}{}{}{}{}{}{}{}{}{}".format(super().getProperties(sep),
                               self.subtype, sep,
                               self.combat, sep,
                               self.queued, sep,
                               self.minimap, sep,
                               self.target, sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return "00:" + self.event._str_time().replace(".",":").strip()
    
    
