import sc2mindshare.analysis
import sc2mindshare.analysis.detectors.detectors
from sc2mindshare.analysis.battle import Battle
from sc2mindshare.analysis.exports.node import X_LD, Node
from sc2mindshare.reader.compat import clean_name, object_text, type_at

# TODO ADD SUPPLY WON 
# TODO WINNER PLAYER

class BattleNode(Battle, Node):

    def __init__(self, p1, p2, startSec, endSec, events, secondsOD, seq, ctx):
        Battle.__init__(self, p1, p2, startSec, endSec, events, secondsOD, ctx)
        Node.__init__(self, seq, fixes=ctx.fixes)

        self.propertiesCount = 7 

    def getNodeTime(self):
        return str(self.startTime)
    
    def getNodePlayer(self) -> str:
        return "Common"

    def getNodeName(self):

        unitPart = ""
        locationPart = ""

        if self.deathCount == 1:
            death = self.deadUnits[0]  # the killer by its type at the kill under N1 (CR-023, D6a)
            killer = type_at(death.killing_unit, death.frame) if "N1" in self.fixes else death.killing_unit.name
            unitPart = "{} killed {}".format(
                clean_name(killer, False, self.fixes), 
                clean_name(self.deadUnits[0].unit.name, False, self.fixes)) #TODO hAXorz, replace str doesn't need to be on event
        elif len(self.killersTypes.items()) == 1:
            for key, value in self.killersTypes.items(): # TODO how to take just one key and value from dict?
                unitPart = "{} {}".format(key, value)
        elif len(self.deadTypes.items()) <= 3:
            for key,value in self.deadTypes.items():
                for unit in value:
                    unitPart += "{}s ".format(unit)
            
            if unitPart == "":
                for key,value in self.deadBuildingsTypes.items():
                    for unit in value:
                        unitPart += "{}s ".format(unit)
            
            unitPart += "died"
        else:
            unitPart = "{} units died".format(self.deathCount) 

        if len(self.basesWhereDeaths) > 0:
            locationPart = " near {} {}".format(object_text(self.basesWhereDeaths[0].player, self.fixes), self.basesWhereDeaths[0])

        return unitPart + locationPart
    
    # TODO MS interface for node outputs across classes
    def getNodeDescription(self):
        desc = ""

        if self.supplyLost[self.player1] > 0:
            desc += "{} lost {} units, {} supply, {} min {} gas.".format(
                self.player1.name, 
                self.p1dc,
                self.supplyLost[self.player1],
                self.minLost[self.player1],
                self.gasLost[self.player1])
        elif self.p1dc > 0:
            desc += "{} lost an {}.".format(self.player1.name, object_text(self.deadUnitsByPlayer[self.player1][0].unit, self.fixes))
        
        if self.supplyLost[self.player2] > 0:
            desc += "{}{}{} lost {} units, {} supply, {} min {} gas.".format(
                X_LD,
                X_LD,
                self.player2.name, 
                self.p2dc,
                self.supplyLost[self.player2],
                self.minLost[self.player2],
                self.gasLost[self.player2])
        elif self.p2dc > 0:
            desc += "{}{} lost an {}.".format(X_LD,self.player2.name, object_text(self.deadUnitsByPlayer[self.player2][0].unit, self.fixes))
        
        if self.startTime == self.endTime:
            desc += "{}{}At {}.".format(X_LD, X_LD, self.startTime)
        else:
            desc += "{}{}From {} to {}.".format(X_LD, X_LD, self.startTime, self.endTime)
        
        return "{} {} {}".format(desc, self.getPlayerBattleDesc(self.player1), self.getPlayerBattleDesc(self.player2))
    
    def getNodeType(self):
        return "Battle"
    
    def getNodeLinks(self): pass

    # props: all deaths, p1 and 2 deaths, start, end time
    def getProperties(self, sep):

        return "{}{}{}{}{}{}{}{}{}{}{}".format(super().getProperties(sep),
                                            self.deathCount, sep,
                                            self.p1dc, sep,
                                            self.p2dc, sep,
                                            self.overallSupply, sep, 
                                            self.endTime, sep)

        # self.addProperty("{} dead units".format(self.player1), self.deadUnitsByPlayer[self.player1])
        # self.addProperty("{} dead units".format(self.player2), self.deadUnitsByPlayer[self.player2])
        
    def addImageDivider(self, imageUrl, position):
        self.images.insert(position, imageUrl)

    # number of dead units, killer units + what they killed, attack command targets
    def getPlayerBattleDesc(self, player):

        # TODO parametrize these functions, util class?
        cgs = ""
        if len(self.controlGroupsUsed[player]) > 0:
            cgs += X_LD + X_LD + "CONTROL GROUPS: "
            for cg in self.controlGroupsUsed[player]:

                # player can press the CG get but there is no CG created for it 
                # TODO the used CGs shouldnt record get if there is no prior set or steal CG
                units = self.ctx.actions.getCgUnits(player, cg, self.endSec)
                if units != None:
                    cgs += "{}{}: {}".format(X_LD, str(cg), units)
        
        kills = ""
        if len(self.killersTypes[player]) > 0:
            kills += X_LD + "KILLS(s): "
            for key, value in self.killersTypes[player].items():
                #the below functions to util class, how to enumerate count dicitonaries, also in CGs.class
                kills += key + str("({})".format(str(value)) if value > 1 else "") + ", "
            kills += X_LD

        bLost = ""
        if len(self.deadBuildingsTypes[player]) > 0:
            bLost += X_LD + "LOST: "
            for key, value in self.deadBuildingsTypes[player].items():
                bLost += key + str("({})".format(str(value)) if value > 1 else "") + ", "

        cas = ""
        if len(self.combatAbilitiesTypes[player]) > 0:
            cas += X_LD + "COMBAT: "
            for key, value in self.combatAbilitiesTypes[player].items():
                cas += key + str("({})".format(str(value)) if value > 1 else "") + ", "
              
        ncas = ""  
        if len(self.nonCombatAbilitiesTypes[player]) > 0:
            ncas += X_LD + "NON-COMBAT: "
            for key, value in self.nonCombatAbilitiesTypes[player].items():
                ncas += key + str("({})".format(str(value)) if value > 1 else "") + ", "

        # if cgs != "" or cas != "" or ncas != "":
        playerHeader = X_LD + X_LD + "===={}====".format(player.name)


        return "{} {} {} {} {} {}".format(playerHeader, kills, bLost, cas, ncas, cgs)