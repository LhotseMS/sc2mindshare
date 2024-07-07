import sc2reader
import sc2reader.mindshare
from sc2reader.mindshare.battle import Battle
import sc2reader.mindshare.detectors
from sc2reader.mindshare.exports.node import Node, X_LD

# TODO ADD SUPPLY WON 
# TODO WINNER PLAYER

class BattleNode(Battle, Node):


    def __init__(self, p1, p2, startSec, endSec, events, secondsOD, seq):
        Battle.__init__(self, p1, p2, startSec, endSec, events, secondsOD)
        Node.__init__(self, seq)

        self.propertiesCount = 5    

    def getNodeTime(self):
        return str(self.startTime)
    
    def getNodePlayer(self) -> str:
        return "Common"

    def getNodeName(self):

        unitPart = ""
        locationPart = ""

        if self.deathCount == 1:
            unitPart = "{} killed {}".format(self.deadUnits[0].killing_unit.name, self.deadUnits[0].unit.name)
        elif len(self.killersTypes.items()) == 1:
            for key, value in self.killersTypes.items(): # TODO how to take just one key and value from dict?
                unitPart = "{} {}".format(key, value)
        elif len(self.deadTypes.items()) <= 3:
            for key,value in self.deadTypes.items():
                for unit in value:
                    unitPart += "{}s ".format(unit)    
            unitPart += "died"
        else:
            unitPart = "{} units died".format(self.deathCount) 

        if len(self.basesWhereDeaths) > 0:
            locationPart = " near {}".format(self.basesWhereDeaths[0])

        return unitPart + locationPart
    
    # TODO MS interface for node outputs across classes
    def getNodeDescription(self):
        desc = ""

        if self.supplyLost[self.player1] > 0:
            desc += "{} lost {} units, {} supply.".format(
                self.player1.name, 
                self.p1dc,
                self.supplyLost[self.player1])
        elif self.p1dc > 0:
            desc += "{} lost an {}.".format(self.player1.name, self.deadUnitsByPlayer[self.player1][0].unit)
        
        if self.supplyLost[self.player2] > 0:
            desc += "{}{} lost {} units, {} supply.".format(
                X_LD,
                self.player2.name, 
                self.p2dc,
                self.supplyLost[self.player2])
        elif self.p2dc > 0:
            desc += "{}{} lost an {}.".format(X_LD,self.player2.name, self.deadUnitsByPlayer[self.player2][0].unit)
        
        if self.startTime == self.endTime:
            desc += "{}At {}.".format(X_LD,self.startTime)
        else:
            desc += "{}From {} to {}.".format(X_LD,self.startTime, self.endTime)
        
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

    # number of dead units, killer units + what they killed, attack command targets
    def getPlayerBattleDesc(self, player):

        # TODO parametrize these functions, util class?
        cgs = ""
        if len(self.controlGroupsUsed[player]) > 0:
            cgs += X_LD + "Control group(s) used: "
            for cg in self.controlGroupsUsed[player]:

                # player can press the CG get but there is no CG created for it 
                # TODO the used CGs shouldnt record get if there is no prior set or steal CG
                units = sc2reader.mindshare.detectors.controlGroupDetector.getCgUnits(player, cg, self.endSec)
                if units != None:
                    cgs += "{}{}: {}".format(X_LD, str(cg), units)
        
        kills = ""
        if len(self.killersTypes[player]) > 0:
            kills += X_LD + "Kill(s): "
            for key, value in self.killersTypes[player].items():
                #the below functions to util class, how to enumerate count dicitonaries, also in CGs.class
                kills += key + str("({})".format(str(value)) if value > 1 else "") + ", "

        bLost = ""
        if len(self.deadBuildingsTypes[player]) > 0:
            bLost += X_LD + "Lost: "
            for key, value in self.deadBuildingsTypes[player].items():
                bLost += key + str("({})".format(str(value)) if value > 1 else "") + ", "

        cas = ""
        if len(self.combatAbilitiesTypes[player]) > 0:
            cas += X_LD + "Combat: "
            for key, value in self.combatAbilitiesTypes[player].items():
                cas += key + str("({})".format(str(value)) if value > 1 else "") + ", "
              
        ncas = ""  
        if len(self.nonCombatAbilitiesTypes[player]) > 0:
            ncas += X_LD + "Non-combat: "
            for key, value in self.nonCombatAbilitiesTypes[player].items():
                ncas += key + str("({})".format(str(value)) if value > 1 else "") + ", "

        if cgs != "" or cas != "" or ncas != "":
            playerHeader = X_LD + X_LD + "===={}====".format(player.name)


        return "{} {} {} {} {} {}".format(playerHeader, kills, bLost, cas, ncas, cgs)