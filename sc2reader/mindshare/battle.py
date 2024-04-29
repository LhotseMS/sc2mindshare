# add focus fire, a moves, abilities
import datetime
import math

from sc2reader.data import *
from sc2reader.events.eventTypes import *
from sc2reader.events.game import *
from sc2reader.events.tracker import *
from termcolor import colored


class Battle():
    """
    This event is recorded for each player at the very beginning of the game before the
    :class:`GameStartEvent`.
    """

    def __init__(self, p1, p2, startSec, endSec, events, secondsOD):
        #:
        self.startSec = startSec
        self.endSec = endSec
        self.events = events
        self.secondsOD = secondsOD
        self.player1 = p1
        self.player2 = p2
        
        self.eventsByPlayer = self.initDictByPlayer()
        self.deadUnitsByPlayer = self.initDictByPlayer()
        self.killersByPlayer = self.initDictByPlayer()
        self.combatAbilitiesByPlayer = self.initDictByPlayer()
        self.nonCombatAbilitiesByPlayer = self.initDictByPlayer()
        self.cameraByPlayer = self.initDictByPlayer()

        self.screens = self.initDictByPlayer()

        
        # BACKLOG
        # - pair CGs to actions
        # - Filter events that took place in the battle 
        # - count other locations that were used during the battle time
        # TODO create comparators for each event type, so that we can limit multi events and duplicated events
        # TODO evaluate who won the battle, generate simple text descriptions based on numbers
        # TODO use chat GPT to generate text overviews of the battles based on learnt data about battles and SC, integration


        # TODO EDGE CASE too long battle 1248-1382 Player 2 - Piliskner (Zerg)
        # Zergling burrows - death?
        # For each battle: action in battle  Ability (5C0) - Attack TargetUnit; TargetPoint;
        # Link CG to selected units, and attack with these units
        # link camera events with movement vectors - measure how much player moves
        # recognize when camera just moved and when was the screen shifter to new screen - length of the shift

        # camera - was a player multitasking, which abilities were cast in the battle
        # Highlight a move - count it Ability (5C0) - Attack; Location: (57.5927734375, 57.080078125, 40920)
        # store locations of creep tumors and check if someone is on creep - how many are there, remove if dead? 
        
        self.losses = {}
        self.losses[self.player1] = SummaryOfDeath(0,0,0)
        self.losses[self.player2] = SummaryOfDeath(0,0,0)
        
        for secOfDying in self.secondsOD:
            for e in secOfDying.events:       
                # print(colored(f"{e} : {self.startSec}-{self.endSec}","magenta")) 

                try:            
                    self.deadUnitsByPlayer[e.unit.owner].append(e)

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
        
        
        self.battleArea = (minX,minY,maxX,maxY,abs(minX-maxX),abs(minY-maxY))
        
        # print(f"minmax {minX} {maxX}, {minY} {maxY}")
        
        self.playersBattleStats = {}
        
        self.statsEventStartSecond = startSec - startSec % 10
        self.statsEventEndSecond = endSec + (10 - endSec % 10)
        
        self.playersBattleStats[self.statsEventStartSecond] = {}
        self.playersBattleStats[self.statsEventEndSecond] = {}



        #group multiclicks
        
        # go through all events assign them to respective dictionaries by type, compute battle properties
        for e in self.events:
            if isinstance(e, CommandEvent) and not isinstance(e, BasicCommandEvent):
                prevCommandEvent = e

                # TODO this shouldnt be if else but classes of processors that determine what to do for each event, parent adding to the same array
                self.eventsByPlayer[e.player].append(e)
                screenEventsBuffer[e.player].append(e)

                if e.has_ability:
                    if e.ability_name in COMBAT_ABILITIES:
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

                    # print(self.replay.players)

            elif isinstance(e, SetControlGroupEvent) or isinstance(e, StealControlGroupEvent):
                self.eventsByPlayer[e.player].append(e)
            #elif isinstance(e, UnitBornEvent): 
            #    self.eventsByPlayer[e.unit_upkeeper].append(e)
                


            # TOOOOOOOODOOOOOOOOOOOOOOOOOOOOOOOOOOO1: TODO: Don't create new screens if the user returned to the previous location, 
            # add function isView in screen to add new camera events to existing screen instead of adding a new one
            # piliskner has no camera events in battle bug    
            elif isinstance(e, CameraEvent) and e.isUnique(self.getLastEvent(lambda x: isinstance(x,CameraEvent))):
                self.cameraByPlayer[e.player].append(e)
                self.eventsByPlayer[e.player].append(e)

                if prevCameraEvent and e.player in prevCameraEvent and (abs(prevCameraEvent[e.player].x - e.x) > 3 or abs(prevCameraEvent[e.player].y - e.y) > 3):
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

            elif (isinstance(e, ControlGroupEvent) or 
                isinstance(e, SelectionEvent)):                 # TODO check and pair selections only of own units with CGs etc
                self.eventsByPlayer[e.player].append(e)

            elif isinstance(e, UnitDiedEvent) and e.countableDeath(): 
                self.eventsByPlayer[e.unit.owner].append(e)
                screenEventsBuffer[e.player].append(e)

                # print(colored(f"{e} : {self.startSec}-{self.endSec}","red"))

            elif isinstance(e, PlayerStatsEvent):
                if e.second == self.statsEventStartSecond:
                    if self.playersBattleStats[self.statsEventStartSecond].get(e.player) == None:
                        self.playersBattleStats[self.statsEventStartSecond][e.player] = list()
                    self.playersBattleStats[self.statsEventStartSecond][e.player] .append(e)
                elif e.second == self.statsEventEndSecond:
                    if self.playersBattleStats[self.statsEventEndSecond].get(e.player) == None:
                        self.playersBattleStats[self.statsEventEndSecond][e.player] = list()
                    self.playersBattleStats[self.statsEventEndSecond][e.player] .append(e)


                # TODO ADD DEATH EVENTS SO WE CAN REPAIR THE DCs
                    

    
    def assignEventToScreen(self, event) -> bool:
        for s in self.screens[event.player]:
            if not s.tryAddEvent(event):
                print("Event not added " + event)
                

    def printPlayerInfo(self, player):
        print(f"Start Stats: {self.playersBattleStats[self.statsEventStartSecond][player][0]}")
        print(f"End Stats: {self.playersBattleStats[self.statsEventEndSecond][player][0]}")
        print(self.losses[player])
        
    # TODO move to util class    
    def initDictByPlayer(self):
        d = {}
        d[self.player1] = list()
        d[self.player2] = list()
        return d
    
    def __str__(self):        
        
        # FULL info
        #print(f"BATTLE===={colored(self.player1, 'green')} vs {colored(self.player2, 'cyan')}=========={datetime.timedelta(seconds=self.startSec)}-{datetime.timedelta(seconds=self.endSec)}=={self._strArea()}==========================================")
        #print(f"=========={colored(self.p1dc,'green')} vs {colored(self.p2dc, 'cyan')}======{self.battleArea}=====================================================================================")
        
        # Dev info
        print(f"BATTLE={colored(datetime.timedelta(seconds=self.startSec),"green")}-{colored(datetime.timedelta(seconds=self.endSec),"green")}=={self._strArea()}={colored(self.p1dc,'green')} vs {colored(self.p2dc, 'cyan')}==={self.battleArea}")        
        
        printDict(self.locations)
        printDict(self.cameraByPlayer)
        printDict(self.eventsByPlayer)
        printDict(self.screens)
        
        # self.printPlayerInfo(self.player1)
        # self.printPlayerInfo(self.player2)
        
        # print(self._strActionsMap())
        # printDict(self.eventsByPlayer)
        # printDict(self.deadUnitsByPlayer)
        
        # printDict(self.eventsByPlayer)
        # printDict(self.combatAbilitiesByPlayer)
        
        # if self.battleRectangle[4] > 20 or self.battleRectangle[5] > 20:
        #     print("====================================================================================================================")
        # printDict(self.deadUnitsByPlayer)
        #     printDict(self.killersByPlayer, "Killers====================================================")
        #     printDict(self.combatAbilitiesByPlayer, "Abilities===================================================")
        #     printDict(self.cameraByPlayer, "Cameras ======")
            #  printDict(self.nonCombatAbilitiesByPlayer, "NCA===================================================")
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


class Screen():

    SCREEN_SIZE = 15 #distance from the center to corner of the screen, exprimentaly determined
    SCREEN_RATIO = 30/22

    def __init__(self, cameraEvents, events = list()):
        self.cameraEvents = cameraEvents
        self.events = list()


        self.vectors = list()
        for i in range(len(self.cameraEvents) - 2):
            self.vectors.append((
                abs(self.cameraEvents[i].x - self.cameraEvents[i+1].x), 
                abs(self.cameraEvents[i].y - self.cameraEvents[i+1].y)))  
            
        for e in events:
            self.tryAddEvent(e)
        
        self.startTime = self.firstView.second
        self.endTime = self.lastView.second

    @property
    def duration(self):
        return self.endTime - self.startTime
    
    @property
    def firstView(self):
        return self.cameraEvents[0]
    
    @property
    def lastView(self):
        return self.cameraEvents[len(self.cameraEvents) - 1]
    
    def tryAddEvent(self, event) -> bool:
        if self.isEventOnScreen(event):
            self.events.append(event)
            return True

        return False

    def isEventOnScreen(self, event) -> bool:
        for c in self.cameraEvents:
            if self.isEventInView(event.x, event.y, c.x, c.y):
                return True
            
        return False
    
    def isEventInView(self, ex, ey, cx, cy, aspect_ratio=1.0):
        # Assume the rectangle's width to height ratio is w:h
        # Calculate width and height using the given distance d
        w = self.SCREEN_SIZE / math.sqrt(1 + (1/aspect_ratio)**2)
        h = w * aspect_ratio

        # Check bounds
        inside_x = (cx - w) <= ex <= (cx + w)
        inside_y = (cy - h) <= ey <= (cy + h)
        
        return inside_x and inside_y

    # TODO consider location proximity computing functions on event
    def __str__(self) -> str:
        return f"Screen {self.firstView.location}-{self.lastView.location}:{len(self.vectors)}xE {self.duration}s"
    
class SummaryOfDeath():
    def __init__(self, minerals, gas, supply):
        self.minerals = minerals
        self.gas = gas
        self.supply = supply
        
    def __str__(self) -> str:
        return f"M: {self.minerals},G: {self.gas},S: {self.supply}"
