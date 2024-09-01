# add focus fire, a moves, abilities
import datetime
import sc2reader.mindshare.detectors.detectors

from sc2reader.data import *
from sc2reader.events.eventTypes import *
from sc2reader.mindshare.utils import MsUtils, PlayerHandler
from sc2reader.mindshare.mindshare import Base
from sc2reader.events.game import *
from sc2reader.events.tracker import *
from sc2reader.mindshare import *
from termcolor import colored


from sc2reader.mindshare.mindshare import Screen


class Battle(PlayerHandler):
    """
    This event is recorded for each player at the very beginning of the game before the
    :class:`GameStartEvent`.
    """

    def __init__(self, p1, p2, startSec, endSec, events, secondsOD):
        #:
        self.events = events

        self.startSec = startSec
        self.endSec = endSec
        self.startTime = datetime.timedelta(seconds=self.startSec)
        self.endTime = datetime.timedelta(seconds=self.endSec)

        self.basesWhereEvents = list()
        self.basesWhereDeaths = list()

        self.secondsOD = secondsOD
        self.player1 = p1
        self.player2 = p2
        
        self.eventsByPlayer = self.initDictByPlayer()
        self.deadUnitsByPlayer = self.initDictByPlayer()
        self.killersByPlayer = self.initDictByPlayer()
        self.combatAbilitiesByPlayer = self.initDictByPlayer()
        self.nonCombatAbilitiesByPlayer = self.initDictByPlayer()
        self.cameraByPlayer = self.initDictByPlayer()
        self.controlGroupsUsed = self.initDictByPlayer()

        self.deadTypes = self.initDictByPlayer(2)
        self.deadBuildingsTypes = self.initDictByPlayer(2)
        self.killersTypes = self.initDictByPlayer(2)
        self.combatAbilitiesTypes = self.initDictByPlayer(2)
        self.nonCombatAbilitiesTypes = self.initDictByPlayer(2)

        self.screens = self.initDictByPlayer()

        self.supplyLost = self.initDictByPlayer(0)
        self.minLost = self.initDictByPlayer(0)
        self.gasLost = self.initDictByPlayer(0)
        
        #/energy spending/
        # larva injects
        # not building workers in the first 
        # larva count too low - relative to max supply
        # creep spread - 
        #unit positions
        # - damaged every 15s
        # - on selection
        # - at target location after not being killed and not having other command 
        #any units cross the map? - segments of map
        #have we scouted anything at all? 
        # - target location vs buildings
        # - 
        #fog of war - list of all current visibility, range from file
        #builds
        #GameSummary
        #APMTracker
        #camera locations if camera returns from far to the exact location of main base
        #count camera hotkeys usage - too few too many? When during multitasking? When macro when not?
        # catching an observer, scan and kill or just kill
        # base blocks - creep, unit on hold, building
        # control of towers - tower coordinates, unit sent there, no other command and didn't die

        #split battles by location - multiprone
        #drone pulls - reaction times
        # recognize screen shortcuts use
        # camera - was a player multitasking - no multitasking during battles, is macro falling behind in battles?
        # fighting on/off creep
        # when player got attacked and wasn't watching - his unit was targetted - opponents camera was on that unit, the attack point


        #staring at a screen for a long time. link camera events with movement vectors - measure how much player moves, 
        # ...recognize when camera just moved and when was the screen shifter to new screen - length of the shift
        # 
        

        # battle desctiption units building and workers died specifically

        # BACKLOG
        # - pair CGs to actions
        # TODO mention in battle that it was a cancellation
        # TODO evaluate who won the battle, generate simple text descriptions based on numbers
        # TODO use chat GPT to generate text overviews of the battles based on learnt data about battles and SC, integration
        # creep spread tracker

        # details 
        # UnitTypeChangeEvent - buildings upgrading
        # Unit born KD8Charge [3C00002] at (157, 73)
        # Track  APM


        # TODO EDGE CASE too long battle 1248-1382 Player 2 - Piliskner (Zerg)
        # Zergling burrows - death?
        # add all burrow type units to deaths
        # For each battle: action in battle  Ability (5C0) - Attack TargetUnit; TargetPoint;

        self.losses = {}
        self.losses[self.player1] = SummaryOfDeath(0,0,0)
        self.losses[self.player2] = SummaryOfDeath(0,0,0)
        
        for secOfDying in self.secondsOD:
            for e in secOfDying.events:       
                # print(colored(f"{e} : {self.startSec}-{self.endSec}","magenta")) 

                try:            
                    self.deadUnitsByPlayer[e.unit.owner].append(e)
                    self.supplyLost[e.unit.owner] += e.unit.supply
                    self.minLost[e.unit.owner] += e.unit.minerals
                    self.gasLost[e.unit.owner] += e.unit.vespene

                    self.losses[e.unit.owner].minerals = self.losses[e.unit.owner].minerals + e.unit.minerals
                    self.losses[e.unit.owner].gas = self.losses[e.unit.owner].gas + e.unit.vespene
                    self.losses[e.unit.owner].supply = self.losses[e.unit.owner].supply + e.unit.supply
                
                    # print(f"Adding {secOfDying.second} {unit} {unit.killing_unit} {unit.type}")
                    if not isinstance(e.unit.killing_unit, Unit):
                        print(colored(f"++++++++++++++ NO KILLING UNIT {datetime.timedelta(seconds=secOfDying.second)}  {e.unit} {e.unit.killing_unit} {e.unit.type}","red"))
                    else:
                        if self.killersByPlayer.get(e.unit.killing_unit.owner) == None:
                            self.killersByPlayer[e.unit.killing_unit.owner] = list()
                        self.killersByPlayer[e.unit.killing_unit.owner].append(e.unit.killing_unit)
                
                except:
                    print(colored(f"++++++++++++++ ERR NO KILLING UNIT {e}", "red"))
        
        self.p1dc = self.deadUnitsByPlayer[self.player1].__len__()
        self.p2dc = self.deadUnitsByPlayer[self.player2].__len__()
        
        minX = 1000
        minY = 1000
        maxX = 0
        maxY = 0
        prevCommandEvent = None

        prevCameraEvent = {}
        cameraEventsBuffer = self.initDictByPlayer()
        screenEventsBuffer = self.initDictByPlayer()
        
        # Dict of all locations that of selected event types
        self.locations = self.initDictByPlayer()
               
        # print(f"minmax {minX} {maxX}, {minY} {maxY}")
        
        self.playersBattleStats = {}
        
        self.statsEventStartSecond = startSec - startSec % 10
        self.statsEventEndSecond = endSec + (10 - endSec % 10)
        
        self.playersBattleStats[self.statsEventStartSecond] = {}
        self.playersBattleStats[self.statsEventEndSecond] = {}

        playerNames = {self.player1.name , self.player2.name}


        #group multiclicks
        
        # go through all events assign them to respective dictionaries by type, compute battle properties
        for e in self.events:
            if isinstance(e, CommandEvent) and not isinstance(e, BasicCommandEvent):
                prevCommandEvent = e

                # TODO this shouldnt be if else but classes of processors that determine what to do for each event, parent adding to the same array
                self.eventsByPlayer[e.player].append(e)
                screenEventsBuffer[e.player].append(e)

                if e.has_ability:
                    if e.isCombat():
                        self.combatAbilitiesByPlayer[e.player].append(e)
                    else:
                        self.nonCombatAbilitiesByPlayer[e.player].append(e)
                    
                # TODO where are the units not just clicks        
                if (isinstance(e, TargetPointCommandEvent) or 
                    isinstance(e, TargetUnitCommandEvent) or 
                    isinstance(e, UpdateTargetPointCommandEvent) or 
                    isinstance(e, UpdateTargetUnitCommandEvent) or 
                    isinstance(e, CommandManagerStateEvent)):
                    if e.location[0] < minX:
                        minX = e.location[0]
                    if e.location[0] > maxX:
                        maxX = e.location[0]
                    if e.location[1] < minY:
                        minY = e.location[1]
                    if e.location[1] > maxY:
                        maxY = e.location[1]                 
                    self.locations[e.player].append(e.location)

                    self.processLocationEvent(e)
                    self.processBaseEvent(e, self.basesWhereEvents)

                    # print(self.replay.players)



            #  TODO: Don't create new screens if the user returned to the previous location, 
            # add function isView in screen to add new camera events to existing screen instead of adding a new one
            # piliskner has no camera events in battle bug    
            elif isinstance(e, CameraEvent) and e.isPlayer(playerNames) and e.isUnique(self.getLastEvent(lambda x: isinstance(x,CameraEvent))):
                self.cameraByPlayer[e.player].append(e)
                self.eventsByPlayer[e.player].append(e)

                # if the next camera event is futther than 3 TODO to constant
                if prevCameraEvent and e.player in prevCameraEvent and (abs(prevCameraEvent[e.player].x - e.x) > 3 and abs(prevCameraEvent[e.player].y - e.y) > 3):
                    self.screens[e.player].append(Screen(cameraEventsBuffer[e.player], screenEventsBuffer[e.player]))

                    screenEventsBuffer[e.player] = list()

                    cameraEventsBuffer[e.player] = list()
                    cameraEventsBuffer[e.player].append(e)
                else:
                    cameraEventsBuffer[e.player].append(e)

                prevCameraEvent[e.player] = e
                
            #lif isinstance(e, CommandManagerStateEvent):
            #    e.commandEvent = lastCommandEvent  
            #    self.eventsByPlayer[e.player].append(e)

            elif isinstance(e, SetControlGroupEvent) or isinstance(e, StealControlGroupEvent):
                self.eventsByPlayer[e.player].append(e)
            #elif isinstance(e, UnitBornEvent): 
            #    self.eventsByPlayer[e.unit_upkeeper].append(e)
                
            elif isinstance(e, ControlGroupEvent):
                self.eventsByPlayer[e.player].append(e) 

                if isinstance(e, GetControlGroupEvent) and e.control_group not in self.controlGroupsUsed[e.player]:
                    self.controlGroupsUsed[e.player].append(e.control_group)


                # checking if the event belongs to player and not observer, id seesm not to be unique across these 2 groups
            elif isinstance(e, SelectionEvent) and e.isPlayer(playerNames):                 # TODO check and pair selections only of own units with CGs etc
                self.eventsByPlayer[e.player].append(e)

            elif isinstance(e, UnitDiedEvent): 
                if e.countableUnitDeath():
                    self.eventsByPlayer[e.unit.owner].append(e)
                    screenEventsBuffer[e.player].append(e)
                    self.processLocationEvent(e)
                    self.processBaseEvent(e, self.basesWhereDeaths)

                # print(colored(f"{e} : {self.startSec}-{self.endSec}","red"))

            elif isinstance(e, PlayerStatsEvent):
                if e.second == self.statsEventStartSecond:
                    if self.playersBattleStats[self.statsEventStartSecond].get(e.player) == None:
                        self.playersBattleStats[self.statsEventStartSecond][e.player] = list()
                    self.playersBattleStats[self.statsEventStartSecond][e.player] .append(e)
                elif e.second == self.statsEventEndSecond:
                    if self.playersBattleStats[self.statsEventEndSecond].get(e.player) == None:
                        self.playersBattleStats[self.statsEventEndSecond][e.player] = list()
                    self.playersBattleStats[self.statsEventEndSecond][e.player].append(e)


                # TODO ADD DEATH EVENTS SO WE CAN REPAIR THE DCs

        
        self.battleArea = (minX,minY,maxX,maxY,abs(minX-maxX),abs(minY-maxY))

        self.allAbilities = (self.nonCombatAbilitiesByPlayer[self.player1] + 
                         self.nonCombatAbilitiesByPlayer[self.player2] + 
                         self.combatAbilitiesByPlayer[self.player1] + 
                         self.combatAbilitiesByPlayer[self.player2])

    @property
    def deathCount(self):
        return self.p1dc + self.p2dc
    
    @property
    def deadUnits(self):
        return self.deadUnitsByPlayer[self.player1] + self.deadUnitsByPlayer[self.player2]
    
    @property
    def overallSupply(self):
        return self.supplyLost[self.player1] + self.supplyLost[self.player2]

    def getCountableDeaths(self):
        return [e for e in self.events if isinstance(e, UnitDiedEvent) and e.countableUnitDeath()] 
                
    # TODO duplicate with detectors
    def otherPlayer(self, player):
        return self.player2 if player == self.player1 else self.player1

    def processBaseEvent(self, e, potentialOwnerList):
        locationBase = sc2reader.mindshare.detectors.detectors.basesDetector.getBaseOnLocation(e)

        if locationBase != None and len([b for b in potentialOwnerList if b.name == locationBase.name]) == 0:
            potentialOwnerList.append(locationBase)

    #categorize events get numbers by type
    #TODO use this logic to group control group units on output
    def processLocationEvent(self, e):
        if isinstance(e, TargetPointCommandEvent) or isinstance(e, TargetUnitCommandEvent):
            if e.isCombat():
                MsUtils.iterateType(self.combatAbilitiesTypes[e.player], e.replaceStrings(e.ability_name, True)) #TODO most of times e.str method is used to get string rep but sometimes its set outside of the event, redo 
            else:
                MsUtils.iterateType(self.nonCombatAbilitiesTypes[e.player],e.replaceStrings(e.ability_name, True))
        elif isinstance(e, UnitDiedEvent) and isinstance(e.unit.killing_unit, Unit):
            if e.buildingDeath():
                MsUtils.iterateType(self.deadBuildingsTypes[e.player], str(e.unit))
            else:
                # TODO the logic of the key (string of unit names) should be somewher else
                MsUtils.iterateType(self.killersTypes[self.otherPlayer(e.player)], e.replaceStrings(e.killing_unit, True) + " killed " + e.replaceStrings(e.unit, True))
                MsUtils.iterateType(self.deadTypes[e.player], e.replaceStrings(e.unit, True)) # TODO maybe we can drop replace strings here as unit should call it now TEST it

    def assignEventToScreen(self, event) -> bool:
        for s in self.screens[event.player]:
            if s.tryAddEvent(event):
                return True
        
        return False
                
    def __str__(self):        
        
        # FULL info
        #print(f"BATTLE===={colored(self.player1, 'green')} vs {colored(self.player2, 'cyan')}=========={datetime.timedelta(seconds=self.startSec)}-{datetime.timedelta(seconds=self.endSec)}=={self._strArea()}==========================================")
        #print(f"=========={colored(self.p1dc,'green')} vs {colored(self.p2dc, 'cyan')}======{self.battleArea}=====================================================================================")
        
        print(f"BATTLE ={colored(self.startTime,"green")}-{colored(self.endTime,"green")}=={self._strArea()}={colored(self.p1dc,'green')} vs {colored(self.p2dc, 'cyan')}==={self.battleArea}")        
                
        return ""

    def _strArea(self):
        str = "x:"
        if self.battleArea[4] > SINGLE_BATTLE_AREA_SIZE[0]:
            str += colored(f"{self.battleArea[4]} : ","red")
        else:
            str += f"{self.battleArea[4]} : "
        
        str += " y:"
        
        if self.battleArea[5] > SINGLE_BATTLE_AREA_SIZE[1]:
            str += colored(f"{self.battleArea[5]}","red")
        else:
            str += f"{self.battleArea[5]}"
        
        return str
    

    def _strActionsMap(self):
        orderedLocs1 = self.locations[self.player1]
        orderedLocs1.sort(key=takeFirst)
        # print(colored(orderedLocs1,"green"))
        
        orderedLocs2 = self.locations[self.player2]
        orderedLocs2.sort(key=takeFirst)
        # print(colored(orderedLocs2,"cyan"))
        
        stepX = (self.battleArea[2] - self.battleArea[0])/20
        stepY = (self.battleArea[3] - self.battleArea[1])/20
        result = ""
        
        minX = self.battleArea[0]
        maxX = minX + stepX
        minY = self.battleArea[1]
        maxY = minY + stepY
        
        gap = 0
        
        while minX < self.battleArea[2]:
        
            xLocations1 = [l for l in orderedLocs1 if minX <= l[0] <= maxX]
            xLocations2 = [l for l in orderedLocs2 if minX <= l[0] <= maxX]
            # print(colored(f"X {minX}-{maxX} - {xLocations1}","green"))
            # print(colored(xLocations2,"cyan"))
            
            result += f"[{str(round(minX,3)).ljust(9)}]"
            
            if xLocations1.__len__() != 0 or xLocations2.__len__() != 0:        
                xLocations1.sort(key=takeSecond)       
                xLocations2.sort(key=takeSecond)
                i = 0
                while minY < self.battleArea[3]:
                    yLoc1 = [l for l in xLocations1 if minY <= l[1] <= maxY]
                    # print(colored(f"Y {minY}-{maxY} - {yLoc1}","green"))
                    yInIntervalLen1 = yLoc1.__len__()
                    if yInIntervalLen1 != 0:
                        result += f"{colored(f'{yInIntervalLen1}','green')}"  
                    else:
                        result += "-"
                        
                    yLoc2 = [l for l in xLocations2 if minY <= l[1] <= maxY]
                    # print(colored(yLoc2,"cyan"))
                    yInIntervalLen2 = yLoc2.__len__()
                    if yInIntervalLen2 != 0:
                        result += f"{colored(f'{yInIntervalLen2}','cyan')}"  
                    else:
                        result += "-"
                        
                    minY += stepY
                    maxY += stepY
                    
                if gap > 3 * stepX:
                    result += f" {gap}"
                gap = 0
            else:
                result += "------------------------------------------"
                gap += stepX # doesnt work TODO
                                
            result += "\n"
            minX += stepX
            maxX += stepX
            minY = self.battleArea[1]
            maxY = minY + stepY
        
        return result

    def printPlayerInfo(self, player):
        print(f"Start Stats: {self.playersBattleStats[self.statsEventStartSecond][player][0]}")
        print(f"End Stats: {self.playersBattleStats[self.statsEventEndSecond][player][0]}")
        print(self.losses[player])
    
    def getLastEvent(self, condition):
        filtered_items = [e for e in self.events if condition(e)]
        # Return the last item if any, or None if the list is empty
        return filtered_items[-1] if filtered_items else None   



def takeFirst(elem):
    return elem[0]   
def takeSecond(elem):
    return elem[1]         
        
def printDict(dict): 
    for key, value in dict.items():
        print(f"\n {key}")
        for e in value:
            print(e)



class SummaryOfDeath():
    def __init__(self, minerals, gas, supply):
        self.minerals = minerals
        self.gas = gas
        self.supply = supply
        
    def __str__(self) -> str:
        return f"M: {self.minerals},G: {self.gas},S: {self.supply}"
