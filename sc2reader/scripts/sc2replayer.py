#!/usr/bin/env python




import string
from sc2reader.data import Unit
from pprint import pprint
from sc2reader.events import *
from sc2reader.factories.plugins.replay import toDict
from sc2reader.mindshare.detectors import BattleDetector, ControlGroupDetector
from termcolor import colored
from pathlib import Path

from datetime import datetime, timedelta

import sys

import argparse
import sc2reader
import sc2reader.mindshare.detectors
from sc2reader.events import *
   

# printer class
    

        

def eventsWithoutPid(event):
    return (isinstance(event,UnitBornEvent) 
            or isinstance(event,UnitTypeChangeEvent) 
            or isinstance(event,UnitDoneEvent) 
            or isinstance(event,UnitDiedEvent) 
            or isinstance(event,UnitPositionsEvent)
            or isinstance(event,UnitInitEvent))
    
    
#class iterator keeps the state of things like deaths
def checkIteration(second, replay):
    # store units died in iteration, look for clusters of dead units - statistics method? 
    # run therough classes of possible plays
    # filter out the events into different categories, camera, clicks, 
    
    deathsCountSequence = 0
    
    
    # for e in greaterSelectionEvents:
    #     print (e)
        
    # printDict(cameraByPlayer, "Cameras")
    
    p2events = list()
        
    for e in [e for e in replay.events if 60 < e.second < 120 ]:
        print(e)
        
        
    # for e in [e for e in replay.events if e.second < 20 ]:
    #     if (isinstance(e, CommandManagerStateEvent) or 
    #         isinstance(e, GetControlGroupEvent) or 
    #         isinstance(e, SelectionEvent) or 
    #         isinstance(e, TargetPointCommandEvent) or 
    #         isinstance(e, TargetUnitCommandEvent) or 
    #         isinstance(e, UpdateTargetPointCommandEvent) or 
    #         isinstance(e, UpdateTargetUnitCommandEvent) or 
    #         isinstance(e, CameraEvent) or 
    #         isinstance(e, DataCommandEvent) or 
    #         isinstance(e, CommandManagerStateEvent)):
    #         if e.pid == 1:
    #             print(e)
    #         else:    
    #             p2events.append(e)
                
    # for e in p2events:
    #     print(e)

    
    
    return 0  

    
def getNonPlayInfo():
    # get Game, Map, Players
    return 0

def getGameWindow(): 
    # byPlayer: list of units, units killed, abilities cast, minerals and vespene lost, targeting(what unit)
    # general: duration, general area
    return 0
    
def printUnits(replay):
    #for unit in [x for x in replay.objects.items() if x.is_army]:
        for key, value in replay.objects.items():
            if value.is_army:
                print("\n")
                print(f"owner {value.owner}"),
                print(f"name {value.name}"),
                print(f"type {value.type}"),
                print(f"race {value.race}"),
                print(f"started_at {value.started_at}"),
                print(f"finished_at {value.finished_at}"),
                print(f"died_at {value.died_at}"),
                print(f"killed_by {value.killed_by}"),
                print(f"killing_player {value.killing_player}"),
                print(f"killing_unit {value.killing_unit}"),
                print(f"killed_units {value.killed_units}"),
                print(f"id {value.id}"),
                print(f"type_history {value.type_history}"),
                print(f"hallucinated {value.hallucinated}"),
                print(f"minerals {value.minerals}"),
                print(f"vespene {value.vespene}"),
                print(f"supply {value.supply}"),
                print(f"is_worker {value.is_worker}"),
                print(f"is_building {value.is_building}"),
                print(f"is_army {value.is_army}")
             
def printDict(dict): 
    for key, value in dict.items():
        print(f"\n {key}")
        for e in value:
            print(e)   

def processFile(filename):
    replay = sc2reader.load_replay(filename, debug=True, load_map=True)
        
    a = toDict()(replay)
    
    print(a)
    print(replay.players)
    
    print(f"Release {replay.release_string}")
    print(f"{replay.type} on {replay.map_name} at {replay.start_time}")
    print("")
    for team in replay.teams:
        print(team)
        for player in team.players:
            print(f"  {player}")
    print("\n--------------------------\n\n")

    print(replay.map.map_info)

    events = replay.events
    # printIntervalAll(0*60,3*60,events)
    # printSomeEvents(events)
    BattleDetector(replay)

    # Allow picking of the player to 'watch'
    #if args.player:
    #    events = replay.player[args.player].events
    #else:
        
    # printUnits(replay)
    #print(.items())
    # u = [x for x in replay.datapack.units.items()]
    # for unt in u:
    #     print(unt)
    
    # printEventsOfInterest(replay, replay.events)
    
    # checkIteration(1705, replay)
    
    
    # Allow specification of events to `show`
    # Loop through the events
    


def printIntervalAll(start, finish, events):

    a = sorted(events, key=lambda event: event.second)

    for event in a:
        if event.second >= start and event.second<= finish:
            if isinstance(event, UnitBornEvent) or isinstance(event, UnitDiedEvent):
                if event.isCounted():
                    print(event)    
            elif (isinstance(event, TargetUnitCommandEvent)
                or isinstance(event, TargetPointCommandEvent)
                or isinstance(event, UpdateTargetPointCommandEvent)
                or isinstance(event, UpdateTargetUnitCommandEvent)
                or isinstance(event, SelectionEvent)
                or isinstance(event, ControlGroupEvent)
                or isinstance(event, CommandEvent)):
                print(event)

def printSomeEvents(events):
    for event in events:

        if hasattr(event,"pid") and event.pid == 1 and (
            isinstance(event, TargetUnitCommandEvent)
            or isinstance(event, TargetPointCommandEvent)
            or isinstance(event, UpdateTargetPointCommandEvent)
            or isinstance(event, UpdateTargetUnitCommandEvent)
            or isinstance(event, CommandEvent)
            or isinstance(event, CameraEvent)
            # or isinstance(event, PlayerLeaveEvent)
            # or isinstance(event, GameStartEvent)
            # or (args.hotkeys and isinstance(event, HotkeyEvent))
            # or (args.cameras and isinstance(event, CameraEvent))
        ):
            u = 2
            print(event)
            
        elif isinstance(event, UnitDiedEvent) and event.countableDeath():
            if event.unit.__str__().startswith("Lurker"):
                print(event)
        elif isinstance(event, SelectionEvent):
            # print(f"\n NEW UNITS {event.new_units} {event.second}")
            
            u = 2
            # getch()
            # if args.bytes:
            #     print("\t" + event.bytes.encode("hex"))



def printEventsOfInterest(replay, events):
    
    
    ustrt = {}
    bases = {}
        
    #a = ControlGroupDetector(replay)
    
    for e in [v for v in events if (isinstance(v, UnitBornEvent) or 
                                    isinstance(v, UnitInitEvent) or 
                                    isinstance(v, UnitDoneEvent))]:
        #if isinstance(e, UnitDoneEvent):
        if not e.unit.owner in bases:
            bases[e.unit.owner] = list()            
        
        if e.unit.name in {"Hatchery","Hive","Lair","Nexus"}:
            if not e.unit in bases[e.unit.owner]:
                bases[e.unit.owner].append(e.unit) 
        #else:
        #    if not e.control_pid in bases:
        #       bases[e.control_pid] = list()
        
        
        
    
    d = {}
    cg = {}
    
    printStats(events)
    print("\n\n")
    printUpgrades(events)
    print("\n\n")
    printBuildings(events)
        
        #if not e.pid in d:
        #    d[e.pid] = list()
        #if not e.pid in cg:
        #    cg[e.pid] = list()
        
        #d[e.pid].append(e)
        
        
                
                       
            
        
    #printDict(d)
    printDict(bases)



def printControlGroups(events):
    
    for e in [v for v in events if (isinstance(v, ControlGroupEvent))]:
        
        if (isinstance(e, SetControlGroupEvent) 
            or isinstance(e, StealControlGroupEvent)):
            print(e.getJson())

def printUpgrades(events):
    #here I bent it a lot
    for e in [v for v in events if (isinstance(v, UpgradeCompleteEvent))]:
        
        omitUnits = ("Reward","Spray","Game")

        if not str(e.upgrade_type_name).startswith(omitUnits):
            print(e.getJson())

def printStats(events):
    #here I bent it a lot
    for e in [v for v in events if (isinstance(v, PlayerStatsEvent))]:
        
        desiredTimes = ("01.04","02.08","03.12","04.16","05.20","06.24","07.28","08.32","09.36","10.40","11.44","12.48","13.52","14.56","16.00","17.04")

        if e._str_prefix().strip().endswith(desiredTimes):
            print(e.getJson())

def printBuildings(events):
    #here I bent it a lot
    buildingNameIndex = {}
    prevTime = "00:00:00"
    currentTime = "00:00:00"

    for e in [v for v in events if (#isinstance(v, SelectionEvent) 
                                    #or isinstance(v, ControlGroupEvent)
                                    #or isinstance(v, TargetUnitCommandEvent)
                                    #or isinstance(v, TargetPointCommandEvent)
                                    #or isinstance(v, UpdateTargetPointCommandEvent)
                                    #or isinstance(v, UpdateTargetUnitCommandEvent)
                                    #or isinstance(v, CommandEvent) or
                                    # isinstance(v, UnitDoneEvent)
                                    #or isinstance(v, UnitBornEvent)
                                    isinstance(v, UnitInitEvent))]:
        
        omitUnits = ("Creep","SupplyDepotLowered")




    
        
        if not str(e.unit).startswith(omitUnits):
            
            output = e.getJson()

            # don't allow same times, breaks the logic downstream, bad workaround TODO
            currentTime = e.getCleanTime()
            buildingName = e.getCleanUnitName()

            if currentTime == prevTime:
                adjustedTime = incrementSeconds(currentTime)
                output = output.replace(currentTime, adjustedTime)
                prevTime = adjustedTime
            else:
                prevTime = currentTime
            

            # append building index so that building dont have the same name
            if buildingNameIndex.get(buildingName) == None: 
                buildingNameIndex[buildingName] = 0
                #print("init " + str(buildingNameIndex.get(buildingName)) + "XX")
            else:
                buildingNameIndex[buildingName] = buildingNameIndex[buildingName] + 1
                #'print("increment " + str(buildingNameIndex[buildingName])+"xx")


            
            if buildingNameIndex[buildingName] != 0:
                # add the building number before ; This should happen in the class
                output = output[:-1] + " " + str(buildingNameIndex[buildingName]) + ";"
                
            print(output)


# todo to util class
def incrementSeconds(time_string: str) -> str:
    # Parse the time string into a datetime object
    time_obj = datetime.strptime(time_string, "%H:%M:%S")
    # Increment the seconds by 1
    time_obj += timedelta(seconds=1)
    # Convert the datetime object back to a string
    incremented_time_string = time_obj.strftime("%H:%M:%S")
    return incremented_time_string


def main():
    parser = argparse.ArgumentParser(
        description="""Step by step replay of game events; shows only the
        Initialization, Command, and Selection events by default. Press any
        key to advance through the events in sequential order."""
    )

    parser.add_argument("FILE", type=str, help="The file you would like to replay")
    parser.add_argument(
        "--player",
        default=0,
        type=int,
        help="The number of the player you would like to watch. Defaults to 0 (All).",
    )
    parser.add_argument(
        "--bytes",
        default=False,
        action="store_true",
        help="Displays the byte code of the event in hex after each event.",
    )
    parser.add_argument(
        "--hotkeys",
        default=False,
        action="store_true",
        help="Shows the hotkey events in the event stream.",
    )
    parser.add_argument(
        "--cameras",
        default=False,
        action="store_true",
        help="Shows the camera events in the event stream.",
    )
    args = parser.parse_args()

    for filename in sc2reader.utils.get_files(args.FILE):
        processFile(filename)
        
        



if __name__ == "__main__":
    main()


try:
    # Assume that we are on *nix or Mac
    import termios
    import fcntl
    import os
    import sys

    def getch():
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
        try:
            while 1:
                try:
                    sys.stdin.read(1)
                    break
                except OSError:
                    pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
            
except ImportError as e:
    try:
        # Oops, we might be on windows, try this one
        from msvcrt import getch
    except ImportError as e:
        # We can't make getch happen, just dump events to the screen
        getch = lambda: True



