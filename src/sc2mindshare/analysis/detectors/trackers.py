
from sc2mindshare.analysis.exports.supplyBlockNode import SupplyBlockNode 
from sc2mindshare.analysis.exports.energyNode import EnergyNode 
from sc2mindshare.analysis.exports.injectNode import InjecDelayNode 
from sc2mindshare.analysis.utils import MsUtils
from sc2mindshare.reader.compat import object_text, type_at
from sc2mindshare.reader.fork_api import Length, UnitDiedEvent
from datetime import datetime, timedelta

import sc2mindshare.analysis.detectors.detectors

from enum import Enum
from sc2mindshare.analysis.text import colored

#: CR-023 S1 (D9a): what each supply provider gives, by its type at the event (S3, S4)
PROVIDERS_AT_EVENT = {
    "Overlord": 8, "Overseer": 8, "OverlordTransport": 8, "OverseerSiegeMode": 8,
    "Pylon": 8, "SupplyDepot": 8, "SupplyDepotLowered": 8,
    "CommandCenter": 15, "OrbitalCommand": 15, "PlanetaryFortress": 15, "Nexus": 15,
    "Hatchery": 6, "Lair": 6, "Hive": 6,
}

#: CR-023 F1: a provider in a mode or a cocoon still provides what its unit did, so its death lowers the limit
#: (a PlanetaryFortress cannot lift; OverseerCocoon is the type history's name for an Overlord's Overseer cocoon)
PROVIDERS_IN_A_MODE = {
    "CommandCenterFlying": 15, "OrbitalCommandFlying": 15, "OverseerCocoon": 8, "TransportOverlordCocoon": 8,
}

class Tracker: 

    def __init__(self, player1, player2, fixes) -> None:

        self.player1 = player1
        self.player2 = player2
        self.fixes = fixes  # CR-023: the layer fixes (the nodes a tracker makes clean their names with them, P2)

        self.seq = 0
        pass

class InjectTracker(Tracker):

    INJECT = "SpawnLarva"
    INJECT_DURATION = 29
    THRESHOLD = 10

    def __init__(self, player1, player2, fixes) -> None:
        super().__init__(player1, player2, fixes)

        self.hatcheries = {}

        self.injectDelays = {}
        self.injectDelays[player1] = list()
        self.injectDelays[player2] = list()

        self.seq = 0

    def addHatchery(self, unit):
        self.hatcheries[unit.id] = list()

    def isHatchery(self, unit):
        return unit.name in ("Hatchery", "Lair", "Hive")

    def isOwnKnownHatchery(self, event):
        """CR-075 (D2a): the event aims at a Hatchery, Lair or Hive this tracker knows, owned by the commanding player.

        A follow-up command carries the previous command's name, so an inject-named event can aim at any unit, an
        opponent's hatchery or a point; only an inject on the player's own known hatchery counts (D1a keeps own
        follow-ups counted)."""
        target = getattr(event, "target", None)
        if target is None or target.id not in self.hatcheries:
            return False
        owner = getattr(target, "owner", None)
        return owner is not None and event.player is not None and owner.pid == event.player.pid

    #TODO time handling should be optimized so that this layer gets the dates and the node one changes it to strings
    def processInject(self, event):

        if not self.isOwnKnownHatchery(event):  # CR-075: skipped, not counted (D2a)
            return

        currentInjectTime = datetime.strptime(event.time, "%M.%S") 
        injectDuration = timedelta(seconds=self.INJECT_DURATION)

        if len(self.hatcheries[event.target.id]) > 0:

            injectDurationUntil = self.hatcheries[event.target.id][-1].injectedUntil
            injectLastingFor = currentInjectTime - injectDurationUntil

            if currentInjectTime > injectDurationUntil:

                if injectLastingFor > timedelta(seconds=self.THRESHOLD):
                    self.injectDelays[event.player].append(InjecDelayNode(event.target, injectDurationUntil.strftime("%M.%S"), currentInjectTime.strftime("%M.%S"), injectLastingFor, self.THRESHOLD, self.seq, fixes=self.fixes))
                    self.seq += 1
                
                injectDurationUntil = currentInjectTime + injectDuration
            else:
                injectDurationUntil = injectDurationUntil + (injectDuration - (-1) * injectLastingFor)
        else:
            injectDurationUntil = currentInjectTime + injectDuration

        self.hatcheries[event.target.id].append(InjectStatus(datetime.strptime(event.time,"%M.%S"), injectDurationUntil))

    def isInjectAbility(self, abilityName):
        return abilityName == self.INJECT

class InjectStatus():

    def __init__(self, injectTime, injectedUntil):
        self.injectTime = injectTime
        self.injectedUntil = injectedUntil

class UnitInfo():

    def __init__(self, unitId, time, x, y):
        self.unitId = unitId
        self.time = time
        self.position = (x, y)
        self.x = x
        self.y = y

class UnitMoveCommand(UnitInfo):

    def __init__(self, unit, time, x, y, travelTime, selectedUnits, selectionEvent, ctx):
        super().__init__(unit.id, time, x, y)
        
        self.unit = unit
        self.selUnits = selectedUnits
        self.selEvent = selectionEvent
        self.travelTime = travelTime

        self.processed = False
        self.targetBase = ctx.bases.getBaseForLocation(x, y)

    @property
    def player(self):
        return self.unit.player
            
class UnitPosition(UnitInfo):

    def __init__(self, unitId, time, x, y, accuracy):
        super().__init__(unitId, time, x, y)
        self.accuracy = accuracy
    
class PositionAccuracy(Enum):
    EXACT = 1
    SCREEN = 2
    PATH = 3
    MAYBE = 4
        
class UnitCommandStatus(UnitPosition):

    def __init__(self, unitId, time, x, y, accuracy):
        super().__init__(unitId, time, x, y, accuracy)

        


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

    UNITS_FROM_STATE_CHANGE = ("OrbitalCommand",)  # CR-023 P12: a tuple (it was a string: a substring test)

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
    
    def __init__(self, player1, player2, fixes):
        super().__init__(player1, player2, fixes)
        
        self.energyHistory = {}
        self.energyUnits = {}  # CR-076 E1: the registered units by id, kept beside their records (the search's candidates)
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
        
        try:
            prevEnergyStatus = None
            for status in self.energyHistory[unit.id]:
                if MsUtils.isLater(time, status.time):
                    break
                prevEnergyStatus = status

            interval = MsUtils.intervalBetween(prevEnergyStatus.time.replace(".",":"), time.replace(".",":"))
            accEnergy = interval * self.ENERGY_REGEN_PS

            return prevEnergyStatus.energy + accEnergy

        except:
            print(f"ERROR unit:{unit}-{unit.id} time: {time}" )
            raise
        
    def registerEnergyUnit(self, unit, time):
        if unit.id not in self.energyHistory:
            self.energyHistory[unit.id] = list()
            self.energyUnits[unit.id] = unit

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
                self.excessEnergy[unit.player].append(EnergyNode(unit, str(Length(seconds=excessStart)), time, energy, excessThreshold, self.seq, fixes=self.fixes))
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

    def casterTypes(self, abilityName):
        """CR-076 E1: the unit types whose abilities hold ``abilityName`` (one for every ability in the table)."""
        return [name for name, abilities in self.UNIT_ABILITIES.items() if abilityName in abilities]

    @staticmethod
    def isStandingAt(unit, time):
        """CR-076 E1: the unit is finished at or before the cast second and not dead at or before it. The check keeps
        a dead unit's record (``removeEnergyUnit`` does nothing), so a dead unit is ruled out here (Vera's E1)."""
        done = getattr(unit, "doneEvent", None)
        if done is None or MsUtils.isLater(time, done.time):  # not done, or done after the cast
            return False
        death = getattr(unit, "deathEvent", None)
        return death is None or MsUtils.isLater(time, death.time)

    def findRealCaster(self, time, abilityName, cost, player, selected):
        """CR-076 E1 (Stefan's D1a, D2a): the cast's caster when the one selected unit has no energy record.

        The candidates are the units the check registered: the commanding player's own, of the ability's caster type,
        standing at the cast, with at least ``cost`` energy by their record. Exactly one: it is the caster. None or
        several: no caster, and one line for the run log (``graph.log``), which names no player."""
        kinds = self.casterTypes(abilityName)
        fit = [
            u for u in self.energyUnits.values()
            if u.name in kinds and player is not None and getattr(u, "owner", None) is not None
            and u.owner.pid == player.pid and self.isStandingAt(u, time) and self.getEnergyAtTime(u, time) >= cost
        ]
        if len(fit) == 1:
            return fit[0]
        found = f"{len(fit)} own" if fit else "no own"
        print(f"energy check: {time} {abilityName}: selected {selected.name} [{selected.id:X}]: data doesn't match "
              f"({found} {'/'.join(kinds)} with {cost} energy)")
        return None

    def processEnergyEvent(self, time, units, abilityName, player=None):
        """``player``: the commanding player (the event's); CR-076 E1 searches only that player's units."""

        for u, abilities in self.UNIT_ABILITIES.items():
            if abilityName in abilities:
                energyChange = abilities[abilityName]
                break

        unit = None
        if len(units) == 1:
            unit = units[0]
            if "E1" in self.fixes and unit.id not in self.energyHistory:  # CR-076 E1: where the fork's check stops
                unit = self.findRealCaster(time, abilityName, energyChange, player, unit)
                if unit is None:
                    return  # kept, charged to no one, logged (D1a, D2a)
        else:
            for u in units:
                # TODO time here is still with ".", it should be replaced for ":" sooner, before it comes here. Refactor time calcualtions add property
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

        # CR-076 E1 (D2a): the spare-energy check only for a type with a threshold; a cast by any other type leaves a
        # running period as it is (Q-F, D1a). The spend is still recorded below.
        if "E1" not in self.fixes or unit.name in self.UNIT_SURPLAS:
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
    def __init__(self, player1, player2, fixes):
        super().__init__(player1, player2, fixes)
        self.addedProviders = set()  # CR-023 S1 (S5): the providers whose limit was added (finished)
        self.providedLimit = {}  # CR-023 S7: player -> the providers' total, which the limit caps at 200

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

    def providerOf(self, e):
        """The supply provider the unit of ``e`` is, or None. CR-023 S1: by its type at the event (S4)."""
        if "S1" in self.fixes:
            name = type_at(e.unit, e.frame)
            if name not in self.providersAtEvent():
                return None
            if isinstance(e, UnitDiedEvent):  # S5: an unfinished provider never raised the limit
                return name if e.unit_id in self.addedProviders else None
            self.addedProviders.add(e.unit_id)
            return name
        name = object_text(e.unit)
        return name if self.isSupplyProvider(name) else None

    def providersAtEvent(self):
        """S1's table of the providers by their type at the event; with F1 (CR-023) the modes and cocoons too."""
        return PROVIDERS_AT_EVENT | PROVIDERS_IN_A_MODE if "F1" in self.fixes else PROVIDERS_AT_EVENT

    def providedBy(self, supplyProvider):
        return (self.providersAtEvent() if "S1" in self.fixes else self.SUPPLY_PROVIDERS)[supplyProvider]

    def getPreviousSupply(self, player):

        if len(self.supplyHistory[player]) > 0:
            return self.supplyHistory[player][-1]
        elif "S1" in self.fixes:  # CR-023 S1 (S1, S2): the starting units and providers are counted as events
            return SupplyStatus("00:00:00", 0, 0)
        else:
            return SupplyStatus("00:00:00", self.INITIAL_SUPPLY, self.INITIAL_LIMIT)

    def changeSupply(self, player, time, change, frame=None):
        prevSupply = self.getPreviousSupply(player)
        self.supplyHistory[player].append(SupplyStatus(time, prevSupply.supply + change, prevSupply.limit, frame))
        
    def increaseLimit(self, player, time, supplyProvider, frame=None):
        self.changeLimit(player, time, self.providedBy(supplyProvider), frame)
    
    def decreaseLimit(self, player, time, supplyProvider, frame=None):
        self.changeLimit(player, time, -self.providedBy(supplyProvider), frame)

    def changeLimit(self, player, time, change, frame=None):
        """The limit moves by ``change``; with S7 (CR-023) it is the providers' total capped at 200, as in the
        game, the total itself still kept (a provider lost above the cap may leave the limit at 200)."""
        prevSupply = self.getPreviousSupply(player)
        if "S7" in self.fixes:
            total = self.providedLimit.get(player, prevSupply.limit) + change
            self.providedLimit[player] = total
            limit = min(total, self.MAX_SUPPLY)
        else:
            limit = prevSupply.limit + change
        self.supplyHistory[player].append(SupplyStatus(time, prevSupply.supply, limit, frame))

    def getSupplyBlocks(self):
        self.findSupplyBlocks(self.player1)
        self.findSupplyBlocks(self.player2)

        return self.supplyBlocks[self.player1] + self.supplyBlocks[self.player2]

    def findSupplyBlocks(self, player):

        blockStart = None
        history = self.supplyHistory[player]
        for index, curStatus in enumerate(history):
            # CR-023 S1 (Q-b2): every event of one loop is applied before a block is judged
            if "S1" in self.fixes and index + 1 < len(history) and history[index + 1].frame == curStatus.frame:
                continue

            if curStatus.supply >= curStatus.limit and blockStart == None and curStatus.supply != self.MAX_SUPPLY:
                blockStart = curStatus

            elif curStatus.supply < curStatus.limit and blockStart != None:
                self.supplyBlocks[player].append(SupplyBlockNode(player, blockStart.time, curStatus.time, self.seq, fixes=self.fixes))
                blockStart = None
                self.seq += 1


    def getSupply(self, player):
        return self.supplyHistory[player].current

class SupplyStatus():

    def __init__(self, time, currentSupply, supplyLimit, frame=None) -> None:
        self.time = time
        self.supply = currentSupply
        self.limit = supplyLimit
        self.frame = frame  # CR-023 S1: the loop of the event, for judging a block once per loop

    def __str__(self) -> str:
        return "{} : {}/{}".format(self.time, self.supply, self.limit)
        

