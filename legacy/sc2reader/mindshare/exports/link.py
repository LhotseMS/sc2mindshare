from sc2reader.mindshare.exports.node import Exportable 
from sc2reader.mindshare.exports.battleNode import BattleNode
from sc2reader.mindshare.exports.unitsNode import UnitsNode
from sc2reader.mindshare.exports.buildingNode import BuildingNode
from sc2reader.mindshare.exports.initNode import InitNode
from sc2reader.mindshare.exports.abilityNode import AbilityNode

# TODO links between buildings that produced/enabled the unit
# TODO link unit transformations
# TODO link Xth bases
# TODO link the same unit types being build through the intervals. Get worker count for workers node. Get current unit count for other units nodes.
class Link(Exportable):

    def __init__(self, n1, n2) -> None:
        self.node1 = n1
        self.node2 = n2
        self.name = None
        self.name1 = None
        self.name2 = None
        self.desc = None
        
        self.propertiesCount = 1

    def getIDs(self, sep) -> str:
        return self.node1.getNodeID() + sep + self.node2.getNodeID() 

    def getName(self, sep) -> str:
        return self.name + sep + "" if self.name != None else self.name1 + sep + self.name2
    
    def getDescription(self) -> str:
        return self.desc
    
    def getProperties(self, sep) -> str:    
        return str(self.direction)


#TODO add classes to link nodes
#name 1 = n2 -> n1
class UnitBattleLink(Link):
    def __init__(self, n1 : BattleNode, n2 : UnitsNode, unitCount) -> None:
        super().__init__(n1, n2)

        self.name1 = "{} died in".format(unitCount)
        self.name2 = "killed {} of".format(unitCount)
        self.desc = "Units start and end"
        self.direction = 0
        
class InitBuildingBattleLink(Link):
    def __init__(self, n1 : BattleNode, n2 : InitNode) -> None:
        super().__init__(n1, n2)

        if n2.cancelled:
            self.name1 = "cancelled during"
        else:
            self.name1 = "destroyed in"
            
        self.name2 = "started during"
        self.desc = "Building that wasn't finished"
        self.direction = 0


class AbilityBattleLink(Link):
    def __init__(self, n1 : BattleNode, n2 : AbilityNode) -> None:
        super().__init__(n1, n2)

        self.name1 = "used during"
        self.name2 = "involved"
        self.desc = "Ability used in battle"
        self.direction = 0


class BuildingBattleLink(Link):
    def __init__(self, n1 : BattleNode, n2 : BuildingNode) -> None:
        super().__init__(n1, n2)

        self.name1 = "razed during"
        self.name2 = "razed"
        self.desc = "Building start and end"
        self.direction = 0

class BattleLink(Link):
    def __init__(self, n1 : BattleNode, n2 : BattleNode) -> None:
        super().__init__(n1, n2)

        self.name1 = "previous"
        self.name2 = "next"
        self.desc = "Two consecutive battles"
        self.direction = 1

class UpgradeLevelLink(Link):
    def __init__(self, n1, n2) -> None:
        super().__init__(n1, n2)

        self.name1 = "previous"
        self.name2 = "next"
        self.desc = "Two consecutive levels of upgrades."
        self.direction = 1

class UpgradeEqLink(Link):
    def __init__(self, n1, n2) -> None:
        super().__init__(n1, n2)

        #TODO fix bug where only name isn't taken in Excel
        self.name1 = "same level"
        self.name2 = "same level"
        self.desc = "Two equivalent upgrades."
        self.direction = 2

class StatsLink(Link):
    def __init__(self, n1, n2) -> None:
        super().__init__(n1, n2)

        self.name = "vs"
        self.desc = "Comparison of players stats from the same time."
        self.direction = 2

class UnitsLink(Link):
    def __init__(self, n1, n2) -> None:
        super().__init__(n1, n2)

        self.name1 = "previous"
        self.name2 = "next"
        self.desc = "same units"
        self.direction = 1
        
class gpLink(Link):
    def __init__(self, n1, n2) -> None:
        super().__init__(n1, n2)

        self.name1 = "played"
        self.name2 = "played by"
        self.desc = "same units"
        self.direction = -1