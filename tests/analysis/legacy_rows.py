"""Test-only renderer: domain models -> the legacy events CSV, to hold CR-012 to G-CSV-1.

It knows the legacy CSV's padding per node kind (MAX_PROPS 15 minus the legacy class's
``propertiesCount``, wrong for some kinds: python bug 5); the domain models do not. The product
never writes this CSV.
"""

from sc2mindshare.domain.models import Graph, Link, Node

MAX_PROPS = 15
#: The legacy classes' propertiesCount per node kind (the padding the CSV shows).
LEGACY_PROPERTIES_COUNT = {
    "Ability": 5,
    "Battle": 7,
    "Building": 3,
    "Chat": 2,
    "Energy Excess": 6,
    "Game": 7,
    "Harrasment": 4,
    "Initiated": 1,
    "Inject Delay": 6,
    "Player": 4,
    "Scouting": 4,
    "Stats": 11,
    "Supply Block": 4,
    "Units": 4,
    "Upgrade": 3,
}
LINK_PROPERTIES_COUNT = 1


def node_row(node: Node) -> str:
    props = ";".join(v for _, v in node.values) + ";"
    pad = ";" * (MAX_PROPS - LEGACY_PROPERTIES_COUNT[node.kind])
    return f"{node.name};{node.description};{node.kind};{node.id};{'|'.join(node.images)};{props};{pad}\n"


def link_row(link: Link) -> str:
    names = f"{link.name};" if link.name is not None else f"{link.name1};{link.name2}"
    pad = ";" * (MAX_PROPS - LINK_PROPERTIES_COUNT)
    return f"{link.node1};{link.node2};{names};{link.description};{link.direction};{pad}\n"


def render(graph: Graph) -> str:
    return "".join(node_row(n) for n in graph.nodes) + "".join(link_row(lk) for lk in graph.links)
