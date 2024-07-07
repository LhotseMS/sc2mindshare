#!/usr/bin/env python

import string
from sc2reader.data import Unit
from pprint import pprint
from sc2reader.events import *
from sc2reader.factories.plugins.replay import toDict
from sc2reader.mindshare.detectors import *
from sc2reader.mindshare.exports.exporter import CSVExporter
from termcolor import colored
from pathlib import Path

import sys

import argparse
import sc2reader
import sc2reader.mindshare.detectors
from sc2reader.mindshare.fileHandler import FileHandler
from sc2reader.events import *
import sc2reader.mindshare.exports.exporter
   

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
    replay = sc2reader.load_replay(FileHandler.REPLAYS_FOLDER + "/" + filename, debug=True, load_map=True)
        
    print(toDict()(replay))

    print(replay.map.map_info)
    

    sc2reader.mindshare.detectors.createDetectors(replay)

    #TODO Messages gl hf and ggs
    exp = CSVExporter(sc2reader.mindshare.detectors.battleDetector.battles + 
                       sc2reader.mindshare.detectors.simpleDetector.upgrades + 
                       sc2reader.mindshare.detectors.simpleDetector.buildings + 
                       sc2reader.mindshare.detectors.simpleDetector.units + 
                       sc2reader.mindshare.detectors.simpleDetector.stats, 
                       sc2reader.mindshare.detectors.simpleDetector.links)

    export = exp.getExport()
    
    #printSomeEvents(replay.events)
    print(replay.active_units)

    fh = FileHandler(replay)
    fh.createEventsFile(export)


def printIntervalAll(start, finish, events):

    a = sorted(events, key=lambda event: event.second)

    for event in a:
        if event.second >= start and event.second<= finish and (
            isinstance(event, SetControlGroupEvent) or 
            isinstance(event, StealControlGroupEvent) or 
            isinstance(event, AddToControlGroupEvent) or 
            isinstance(event, SelectionEvent)):
            #if event.control_group != 10:
            if event.pid == 0:
                print(str(event))

def printSomeEvents(events):
    for event in events:

        if isinstance(event, PlayerStatsEvent):
            # or isinstance(event, PlayerLeaveEvent)
            # or isinstance(event, GameStartEvent)
            # or (args.hotkeys and isinstance(event, HotkeyEvent))
            # or (args.cameras and isinstance(event, CameraEvent))
            print(event)
            

def printEventsOfInterest(replay, events):
        
    ustrt = {}
    bases = {}
        
    #a = ControlGroupDetector(replay)
    
    for e in [v for v in events if (isinstance(v, UnitBornEvent) or 
                                    isinstance(v, UnitDoneEvent))]:
        
        # not building,  
        # born: time not 00, Unit born Larva, Unit born Broodling 
        # done: shield battery
        # Unit Extractor Rich done
        
        if not e.unit.is_building and e.time != "00:00":
            print(e)
       
        #else:
        #    if not e.control_pid in bases:
        #       bases[e.control_pid] = list()
        
        
        
    
        
        #if not e.pid in d:
        #    d[e.pid] = list()
        #if not e.pid in cg:
        #    cg[e.pid] = list()
        
        #d[e.pid].append(e)
        
        
                
                       
            
        
    #printDict(d)



def printControlGroups(events):
    
    for e in [v for v in events if (isinstance(v, ControlGroupEvent))]:
        
        if (isinstance(e, SetControlGroupEvent) 
            or isinstance(e, StealControlGroupEvent)):
            print(e.getJson())


# todo to util class


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



