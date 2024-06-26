
from sc2reader.mindshare.exports.node import SimpleNode, X_LD
from sc2reader.events.tracker import PlayerStatsEvent

class StatsNode(SimpleNode):

    def __init__(self, e : PlayerStatsEvent, seq) -> None:
        super().__init__(e, seq)
        self.propertiesCount = 11
        self.type = "Stats"

    def getNodeName(self):
        return "{} {}".format(self.getNodeTime(), self.getNodePlayer())
    
    # TODO time from last upgrade, player completed upgrade at time 
    def getNodeDescription(self):
        return "{} had these stats at {}:{}{}{}".format(self.getNodePlayer(),
                           self.getNodeTime(),
                           X_LD,X_LD,
                           (
                            f"Current: {self.event.minerals_current}m {self.event.vespene_current}g" + X_LD +   
                            f"Rate: {self.event.minerals_collection_rate}m {self.event.vespene_collection_rate}g" + X_LD +  
                            f"Work: {self.event.workers_active_count}" + X_LD +  
                            f"Army: {self.event.minerals_used_current_army}m {self.event.vespene_used_current_army}g" + X_LD + 
                            f"Eco: {self.event.minerals_used_current_economy}m {self.event.vespene_used_current_economy}g" + X_LD +  
                            f"Tech: {self.event.minerals_used_current_technology}m {self.event.vespene_used_current_technology}g" 
                        ))
    
    def getProperties(self, sep):
        return "{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}{}".format(super().getProperties(sep),
                self.event.minerals_current, sep,  
                self.event.vespene_current, sep, 
                self.event.minerals_collection_rate, sep, 
                self.event.vespene_collection_rate, sep, 
                self.event.workers_active_count, sep, 
                self.event.minerals_used_current_army, sep, 
                self.event.vespene_used_current_army, sep,
                self.event.minerals_used_current_economy, sep, 
                self.event.vespene_used_current_economy, sep, 
                self.event.minerals_used_current_technology, sep, 
                self.event.vespene_used_current_technology, sep)
    
    # TODO link to related opponent upgrade, previous upgrade
    def getNodeLinks(self) -> str: pass

    def getNodeTime(self):
        return "00:" + self.event._str_prefix().replace(".",":").strip()
    



