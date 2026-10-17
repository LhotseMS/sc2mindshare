from sc2reader.mindshare.exports.node import Exportable, Node
from sc2reader.mindshare.exports.battleNode import BattleNode
from sc2reader.mindshare.exports.link import Link, UnitsLink



class Exporter:

    nodes = None
    links = None    

    def __init__(self, n : list[Node], l : list[Link]) -> None:
        self.nodes = n
        self.links = l
        pass

    def getExport() -> str:pass
    def getAllLinks() -> str:pass
    def getLink() -> str:pass
    def getAllNodes() -> str:pass
    def getNode() -> str: pass
    def getLink() -> str: pass


class CSVExporter(Exporter):

    SEPARATOR = ";"
    MAX_PROPS = 15

    def __init__(self, n: list[Node], l: list[Link]) -> None:
        super().__init__(n, l)

    def getHeaders(self):
        return "Name{}Description{}Type{}ID{}Links{}Time{}Player".format(*(self.SEPARATOR,) * 6)
    
    def battleHeaders(self):
        #TODO add players names, currently they should be set manually in excel after export
        return "units lost{}P1 lost{}P2 lost{}start{}end{}P1 dead units{}P2 dead units{}".format(*(self.SEPARATOR,) * 7 )
    
    
    def spaceOutProperties(self, exp : Exportable):
        return exp.getProperties(self.SEPARATOR) + self.SEPARATOR + self.emptyProps(exp.propertiesCount)

    def emptyProps(self, count):
        return "".join([self.SEPARATOR for _ in range(self.MAX_PROPS - count)])

    def getExport(self):
        #exportStr = self.getHeaders()
        exportStr = self.getAllNodes()
        exportStr += self.getAllLinks()

        return exportStr

    def getAllLinks(self):
        linksStr = ""
        for lnk in self.links:
            linksStr += self.getLink(lnk)
        return linksStr

    def getLink(self, lnk : UnitsLink):
        
        lnkStr = lnk.getIDs(self.SEPARATOR) + self.SEPARATOR
        lnkStr += lnk.getName(self.SEPARATOR) + self.SEPARATOR
        lnkStr += lnk.getDescription() + self.SEPARATOR
        
        lnkStr += self.spaceOutProperties(lnk) + "\n"

        return lnkStr

    def getAllNodes(self):
        nodesStr = ""
        for node in self.nodes:
            nodesStr += self.getNode(node)
        return nodesStr
        
    def getNode(self, node : Node) -> str: 

        nodeStr = node.getNodeName() + self.SEPARATOR
        nodeStr += node.getNodeDescription() + self.SEPARATOR
        nodeStr += node.getNodeType() + self.SEPARATOR
        nodeStr += node.getNodeID() + self.SEPARATOR

        nodeStr += node.getNodeImages() + self.SEPARATOR 

        nodeStr += self.spaceOutProperties(node) + "\n"
        
        return nodeStr

class JSONExporter(Exporter):

    def getAllNodes():pass
        
    def getNode(self, node : Node, seq): 
        nodeStr = "{"

        nodeStr += "\"{}\":\"{}\"".format(self.KEY_ID, node.getNodeIDBase() + seq) + ","
        nodeStr += "\"{}\":\"{}\"".format(self.KEY_TYPE, node.getNodeType() + seq) + ","
        nodeStr += "\"{}\":\"{}\"".format(self.KEY_NAME, node.getNodeName() + seq) + ","
        nodeStr += "\"{}\":\"{}\"".format(self.KEY_DESC, node.getNodeDescription() + seq) + ","
        nodeStr += "\"{}\":{}".format(self.KEY_PROPERTIES, node.getProperties() + seq)
        nodeStr += "}"

        return nodeStr

    
    
