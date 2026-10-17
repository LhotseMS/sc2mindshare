
from pprint import pprint
from sc2reader.mindshare.detectors.detectors import *
from sc2reader.mindshare.exports.exporter import CSVExporter


import argparse
import sc2reader
import sc2reader.mindshare.detectors.detectors
from sc2reader.mindshare.fileHandler import FileHandler
from sc2reader.events import *
import sc2reader.mindshare.exports.exporter

def parseReplay(filename):
    replay = sc2reader.load_replay(FileHandler.REPLAYS_FOLDER + "/" + filename, debug=True, load_map=True)
            
    sc2reader.mindshare.detectors.detectors.createDetectors(replay)

    exp = CSVExporter(sc2reader.mindshare.detectors.detectors.singlesDetector.nodes +
                      sc2reader.mindshare.detectors.detectors.battleDetector.battles + 
                      sc2reader.mindshare.detectors.detectors.battleDetector.harrasmentNodes + 
                      sc2reader.mindshare.detectors.detectors.simpleDetector.upgrades + 
                      sc2reader.mindshare.detectors.detectors.simpleDetector.buildings + 
                      sc2reader.mindshare.detectors.detectors.simpleDetector.initializations + 
                      sc2reader.mindshare.detectors.detectors.simpleDetector.units + 
                      sc2reader.mindshare.detectors.detectors.simpleDetector.stats + 
                      sc2reader.mindshare.detectors.detectors.simpleDetector.abilities +  
                      sc2reader.mindshare.detectors.detectors.simpleDetector.messages +  
                      sc2reader.mindshare.detectors.detectors.simpleDetector.supplyBlocks +
                      sc2reader.mindshare.detectors.detectors.actionsDetector.excessEnergy +
                      sc2reader.mindshare.detectors.detectors.actionsDetector.injectDelays +
                      sc2reader.mindshare.detectors.detectors.actionsDetector.scouting, 

                      sc2reader.mindshare.detectors.detectors.singlesDetector.links +
                      sc2reader.mindshare.detectors.detectors.battleDetector.links +
                      sc2reader.mindshare.detectors.detectors.simpleDetector.links)

    export = exp.getExport()

    fh = FileHandler(replay)
    fh.createEventsFile(export)
    

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Script to create capture game video for a player and create screenshots from that')
    parser.add_argument('--replay', type=str, help='Name of the replay file')
    
    args = parser.parse_args()

    parseReplay(args.replay)