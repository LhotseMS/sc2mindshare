
from sc2reader.mindshare.exports.supplyBlockNode import SupplyBlockNode 
from sc2reader.mindshare.exports.energyNode import EnergyNode 
from sc2reader.mindshare.exports.injectNode import InjecDelayNode 
from sc2reader.mindshare.utils import MsUtils
from sc2reader.utils import Length
from datetime import datetime, timedelta

from termcolor import colored

class Tracker: 

    def __init__(self, player1, player2) -> None:

        self.player1 = player1
        self.player2 = player2

        self.seq = 0
        pass

class InjectTracker(Tracker):

    INJECT = "SpawnLarva"
    INJECT_DURATION = 29
    THRESHOLD = 10

    def __init__(self, player1, player2) -> None:
        super().__init__(player1, player2)

        self.hatcheries = {}

        self.injectDelays = {}
        self.injectDelays[player1] = list()
        self.injectDelays[player2] = list()

        self.seq = 0

    def addHatchery(self, unit):
        self.hatcheries[unit.id] = list()

    def isHatchery(self, unit):
        return unit.name in ("Hatchery", "Lair", "Hive")

    #TODO time handling should be optimized so that this layer gets the dates and the node one changes it to strings
    def processInject(self, event):

        currentInjectTime = datetime.strptime(event._str_time(), "%M.%S") 
        injectDuration = timedelta(seconds=self.INJECT_DURATION)

        if len(self.hatcheries[event.target.id]) > 0:

            injectDurationUntil = self.hatcheries[event.target.id][-1].injectedUntil
            injectLastingFor = currentInjectTime - injectDurationUntil

            if currentInjectTime > injectDurationUntil:

                if injectLastingFor > timedelta(seconds=self.THRESHOLD):
                    self.injectDelays[event.player].append(InjecDelayNode(event.target, injectDurationUntil.strftime("%M.%S"), currentInjectTime.strftime("%M.%S"), injectLastingFor, self.THRESHOLD, self.seq))
                    self.seq += 1
                
                injectDurationUntil = currentInjectTime + injectDuration
            else:
                injectDurationUntil = injectDurationUntil + (injectDuration - (-1) * injectLastingFor)
        else:
            injectDurationUntil = currentInjectTime + injectDuration

        self.hatcheries[event.target.id].append(InjectStatus(datetime.strptime(event._str_time(),"%M.%S"), injectDurationUntil))

    def isInjectAbility(self, abilityName):
        return abilityName == self.INJECT

class InjectStatus():

    def __init__(self, injectTime, injectedUntil):
        self.injectTime = injectTime
        self.injectedUntil = injectedUntil

        


class EnergyTracker(Tracker):

    #TODO multiple units don't consider upgrades or time based energy spenditure
    # CalldownMULE ChronoBoost SpawnLarva
    UNIT_ABILITIES = {
        "Nexus": {"ChronoBoostEnergyCost": 50, "StrategicRecall": 50, "Battery": 50, "Overcharge": 50},
        "ShieldBattery": {"Restore": 50},
        "Sentry": {"ForceField": 50, "GuardianShield": 75, "Hallucination": 75},
        "HighTemplar": {"Feedback": 50, "PsionicStorm": 75},
        "Oracle": {"Revelation": 25, "StasisWard": 50, "ActivatePulsarBeam": 30},
        "Phoenix": {"GravitonBeam": 50},
        "OrbitalCommand": {"CalldownMULE": 50,"ExtraSupplies": 50, "ScannerSweep": 50},
        "Ghost": {"SteadyTargeting": 50, "EMPRound": 75},
        "Medivac": {"BuildAutoTurret": 50, "InterferenceMatrix": 75, "AntiArmorMissile": 75},
        "Queen": {"SpawnLarva": 25, "SpawnCreepTumor": 25, "Transfusion": 50},
        "Overseer": {"SpawnChangeling": 50, "Contaminate": 125},
        "Infestor": {"FungalGrowth": 75, "NeuralParasite": 100, "MicrobialShroud": 75},
        "Viper": {"BlindingCloud": 100, "ParasiticBomb": 125}
    }

    UNITS_FROM_STATE_CHANGE = ("OrbitalCommand")

    UNIT_SURPLAS = {
        "Nexus": {3:50, 6:50, 12:100},
        "OrbitalCommand": {3:50, 6:50, 12:100},
        "Queen": {3:25, 6:100, 12:100}
    }

    UNIT_INITIAL = {
        "ShieldBattery": 100,
        "Ghost": 75,
        "Queen": 25
    }

    DEFAULT_ENERGY = 50
    ENERGY_CAP = 200
    ENERGY_REGEN_PS = 0.7905 #added 0.003
    ENERGY_ANGLE = 38.33
    TOLLERABLE_excess_INTERVAL = 2
    
    def __init__(self, player1, player2):
        super().__init__(player1, player2)
        
        self.energyHistory = {}
        self.excessEnergy = {}
        self.excessEnergy[player1] = list()
        self.excessEnergy[player2] = list()
        self.seq = 0

    def isEnergyUnit(self, unit):
        return unit.name in self.UNIT_ABILITIES and unit.name not in self.UNITS_FROM_STATE_CHANGE
    
    def isEnergyUpgrade(self, unit):
        return unit.name in self.UNITS_FROM_STATE_CHANGE

    def isEnergyAbility(self, abilityName):
        for unit, abilities in self.UNIT_ABILITIES.items():
            if abilityName in abilities:
                return True

        #print("Not an energy ability: " + abilityName)
        return False

    def getEnergyAtTime(self, unit, time): 

        prevEnergyStatus = None
        for status in self.energyHistory[unit.id]:
            if MsUtils.isLater(time, status.time):
                break
            prevEnergyStatus = status

        interval = MsUtils.intervalBetween(prevEnergyStatus.time.replace(".",":"), time.replace(".",":"))
        accEnergy = interval * self.ENERGY_REGEN_PS

        return prevEnergyStatus.energy + accEnergy
        
    def registerEnergyUnit(self, unit, time):
        if unit.id not in self.energyHistory:
            self.energyHistory[unit.id] = list()

            if unit.name in self.UNIT_INITIAL:
                initEnergy = self.UNIT_INITIAL[unit.name]
            else:
                initEnergy = self.DEFAULT_ENERGY

            self.energyHistory[unit.id].append(EnergyStatus(time, initEnergy, "", unit))

            #print("Energy unit added {}: {} {}".format(time, unit.name, unit.id))

    def removeEnergyUnit(self, unitID):
        try:
            a =""
            #self.energyHistory[unitID].append("DIED")
        except:
            print("Unit not added: " + str(unitID)) 

    def getThreshold(self, time, unit):

        currentSec = MsUtils.timeToSeconds(time)

        if currentSec <= 3*60:
            excessThreshold = self.UNIT_SURPLAS[unit.name][3]
        elif currentSec <= 6*60:
            excessThreshold = self.UNIT_SURPLAS[unit.name][6]
        else:
            excessThreshold = self.UNIT_SURPLAS[unit.name][12]

        return excessThreshold

    def detectEnergyexcess(self, unit, time, energy) -> bool:

        if unit.name not in self.UNIT_SURPLAS:
            return False

        excessThreshold = self.getThreshold(time, unit)

        if energy >= excessThreshold:
            excessStart = MsUtils.calculateY1(MsUtils.timeToSeconds(time), excessThreshold, energy, self.ENERGY_ANGLE)
            if MsUtils.intervalBetween(str(Length(seconds=excessStart)), time) > self.TOLLERABLE_excess_INTERVAL:
                self.excessEnergy[unit.player].append(EnergyNode(unit, str(Length(seconds=excessStart)), time, energy, excessThreshold, self.seq))
                self.seq += 1
                return True
            else:
                return False
        else:
            return False        

    def endEnergyexcess(self, player, endTime):
        self.excessEnergy[player][-1].setEnd(endTime)

    def isexcessActive(self, player) -> bool:
        return len(self.excessEnergy[player]) > 0 and self.excessEnergy[player][-1].end == None

    def processEnergyEvent(self, time, units, abilityName):

        for u, abilities in self.UNIT_ABILITIES.items():
            if abilityName in abilities:
                energyChange = abilities[abilityName]
                break
                    
        unit = None
        if len(units) == 1:
            unit = units[0]
        else:
            for u in units:
                # TODO time her is still with ".", it should be replaced for ":" sooner, before it comes here. Refactor time calcualtions add property
                if (u.doneEvent != None and 
                    MsUtils.isLater(u.doneEvent.time, time.replace(".",":")) and 
                    u.id in self.energyHistory and 
                    self.getEnergyAtTime(u, time) >= energyChange): # not done units are included in the control groups, and nexus gets picked up before the done event.
                    unit = u
                    break

        if unit is None:
            print(colored("No unit found {} {} {}".format(time, units, abilityName))) # probably double click before energy resolved
            return

        currentEnergy = self.getEnergyAtTime(unit, time)

        newEnergy = currentEnergy - energyChange

        if self.isexcessActive(unit.player):
            if newEnergy <= self.getThreshold(time, unit):
                self.endEnergyexcess(unit.player, time)
        else:
            self.detectEnergyexcess(unit, time, currentEnergy)
            if self.isexcessActive(unit.player) and newEnergy <= self.getThreshold(time, unit):
                self.endEnergyexcess(unit.player, time)
        

        self.energyHistory[unit.id].append(EnergyStatus(time, newEnergy, abilityName, unit))

        #if unit.id in (77594625, 65798145):
        #totalTimeAlive = MsUtils.intervalBetween("00:00", time.replace(".",":"))
        #totalAccEnergy = totalTimeAlive * self.ENERGY_REGEN_PS
        #print(colored("{} {}({}) {}:{}en, cur {}. Ttl {}".format(time, unit.name, unit.id, abilityName, energyChange, newEnergy, totalAccEnergy), "green"))
        #print(colored("{} {} {}".format(time, prevEnergy - energyChange, totalAccEnergy), "green"))


class EnergyStatus():

    def __init__(self, time, current, abilityName, unit) -> None:

        self.time = time
        self.energy = current
        self.abilityName = abilityName
        self.uName = unit.name
        self.uId = unit.id
        pass

    def __str__(self) -> str:
        return "{} {}({}) did {} for {} energy".format(self.time, self.uName, self.uId, self.abilityName, self.energy)
        

class SupplyTracker(Tracker):

    INITIAL_SUPPLY = 12
    INITIAL_LIMIT = 15
    MAX_SUPPLY = 200
    SUPPLY_PROVIDERS = {
        "Overlord" : 8,
        "Pylon" : 8,
        "Supply Depot" : 8,
        "Supply Depot Lowered" : 8,
        "ADDON" : 8,
        "Command Center" : 15,
        "Orbital Command" : 15,
        "Nexus" : 15,
        "Hatchery" : 15 
    }

    def __init__(self, player1, player2):
        super().__init__(player1, player2)

        self.supplyHistory = {}
        self.supplyHistory[player1] = list()
        self.supplyHistory[player2] = list()

        self.supplyBlocks = {}
        self.supplyBlocks[player1] = list()
        self.supplyBlocks[player2] = list()

    def isSupplyProvider(self, gameName) -> bool:

        for name, supply in self.SUPPLY_PROVIDERS.items():
            if name == gameName:
                #print("Supply provider")
                return True

        return False

    def getPreviousSupply(self, player):

        if len(self.supplyHistory[player]) > 0:
            return self.supplyHistory[player][-1]
        else:
            return SupplyStatus("00:00:00", self.INITIAL_SUPPLY, self.INITIAL_LIMIT)

    def changeSupply(self, player, time, change):
        prevSupply = self.getPreviousSupply(player)
        self.supplyHistory[player].append(SupplyStatus(time, prevSupply.supply + change, prevSupply.limit))
        
    def increaseLimit(self, player, time, supplyProvider):
        prevSupply = self.getPreviousSupply(player)
        self.supplyHistory[player].append(SupplyStatus(time, prevSupply.supply, prevSupply.limit + self.SUPPLY_PROVIDERS[supplyProvider]))
    
    def decreaseLimit(self, player, time, supplyProvider):
        prevSupply = self.getPreviousSupply(player)
        self.supplyHistory[player].append(SupplyStatus(time, prevSupply.supply, prevSupply.limit - self.SUPPLY_PROVIDERS[supplyProvider]))

    def getSupplyBlocks(self):
        self.findSupplyBlocks(self.player1)
        self.findSupplyBlocks(self.player2)

        return self.supplyBlocks[self.player1] + self.supplyBlocks[self.player2]

    def findSupplyBlocks(self, player):

        blockStart = None
        for curStatus in self.supplyHistory[player]:

            if curStatus.supply >= curStatus.limit and blockStart == None and curStatus.supply != self.MAX_SUPPLY:
                blockStart = curStatus

            elif curStatus.supply < curStatus.limit and blockStart != None:
                self.supplyBlocks[player].append(SupplyBlockNode(player, blockStart.time, curStatus.time, self.seq))
                blockStart = None
                self.seq += 1


    def getSupply(self, player):
        return self.supplyHistory[player].current

class SupplyStatus():

    def __init__(self, time, currentSupply, supplyLimit) -> None:
        self.time = time
        self.supply = currentSupply
        self.limit = supplyLimit

    def __str__(self) -> str:
        return "{} : {}/{}".format(self.time, self.supply, self.limit)
        

