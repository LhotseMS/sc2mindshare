"""Every layout constant, with its source in the workbook's Positioner (layout-spec.md §4).

Lane offsets are literals (Python shows ``2.145 * 3.2 = 6.864000000000001``; spec §2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Timeline = Literal["compressed", "linear"]


@dataclass(frozen=True)
class Profile:
    timeline: Timeline = "compressed"
    window_s: int = 10  # P:239, P:656
    row_pitch: float = 2.5  # singleIntervalHeight, P:252
    lane_battle: float = 0.0  # P:312
    lane_chat: float = 3.84  # 1.2 x 3.2, P:169
    lane_stats: float = 5.76  # 1.8 x 3.2, P:165
    lane_clock: float = 5.76  # P:571, P:581 (the stats band)
    lane_ability: float = 6.864  # 2.145 x 3.2, P:161
    lane_building: float = 8.0  # 2.5 x 3.2, P:157 (Building, Upgrade, Initiated)
    building_stack_step: float = 1.05  # bAuRowHeight, P:263
    building_stack_free: int = 5  # P:501, P:521
    lane_supply_block: float = 12.16  # 3.8 x 3.2, P:153
    lane_units: float = 12.8  # 4 x 3.2, inner edge, P:149
    battle_shift_threshold: float = 1.6  # P:333 (radius of the current battle)
    battle_gap: float = 0.3  # P:714
    battle_shift_limit: float = 5.76  # P:339 (the stats lane, side B)
    unit_max_lag_windows: int = 3  # the intent of P:478 (B1)
    anchor_game: tuple[float, float] = (-12.0, 0.0)  # P:271
    anchor_players: tuple[tuple[float, float], tuple[float, float]] = ((-6.0, -9.0), (-6.0, 9.0))  # P:272-273
    # stream 2's node types (spec §13, CR-015; TD-44, TD-45)
    anchor_coaching: tuple[tuple[float, float], tuple[float, float]] = ((-6.0, -11.5), (-6.0, 11.5))  # §13.2
    anchor_build_comparison: tuple[tuple[float, float], tuple[float, float]] = ((-6.0, -14.0), (-6.0, 14.0))  # §13.2
    ghost_skip_slot: int = 4  # §13.3 rule 5: slot 4 overlaps the supply-block band
    rail_height: float = 0.6  # §13.4, P0-6 §4.5
    rail_clearance: float = 0.5  # §13.4, beyond the widest unit row
    unit_spread_floor: float = 5.8  # §13.4: M_side >= 5.8
    # CR-073: the timeline lanes beyond the rail band (Leo's Algorithm notes, points 3 and 4; D1a)
    lane_clearance: float = 0.3  # between the rail band and the events lane, and between two lanes
    event_step: float = 1.05  # one stacked card to the next (card height 1.0 + 0.05)
    bar_height: float = 1.0  # D1a: the supply-block height
    bar_gap: float = 0.05  # between two stacked bars
    grid_origin: tuple[float, float] = (15.0, 0.0)  # P:688
    grid_step: float = 3.0  # P:749-767
    grid_columns: int = 4
    clock_size: tuple[float, float] = (1.1, 0.75)  # IMG:28
    fixed_sizes: dict[str, object] = field(
        default_factory=lambda: {
            "Ability": [1.6, 0.88],  # SRN:130
            "Stats": [2.65, 1.28],  # SRN:149
            "Game": [10, 3.3],  # SRN:163
            "Player": [7.8, 2.2],  # SRN:166
            "Coaching": [7.8, 2.2],  # spec §13.2 (the Player card's size)
            "Build Comparison": [7.8, 2.2],  # spec §13.2
        }
    )
    default_size: tuple[float, float] = (2.65, 1)  # SRN:100


#: Node kinds per bucket (spec §5.1).
BAU = frozenset({"Building", "Upgrade", "Initiated"})
SINGLE_POINT = {"Stats": "lane_stats", "Chat": "lane_chat", "Ability": "lane_ability"}
OCCUPYING = frozenset({"Battle", "Stats", "Chat", "Ability"}) | BAU
#: Stream 2's node types (spec §13; TD-41): player-column cards, building-stack ghosts, the interval rail.
CARDS = {"Coaching": "anchor_coaching", "Build Comparison": "anchor_build_comparison"}
GHOSTS = ("Missing Step", "Checkpoint")  # in this order when they tie (§13.3 rule 3)
RAIL = frozenset({"Scouting Gap"})
#: CR-073: the timeline lanes of each side, from the units outward: the events lane (cards at their start),
#: then the inject-delay and spare-energy lanes (bars over their period). Never occupying, like the rail.
TIMELINE_LANES = {"Scouting": "events", "Harrasment": "events", "Inject Delay": "inject", "Energy Excess": "energy"}
LANE_ORDER = ("events", "inject", "energy")
BAR_LANES = frozenset({"inject", "energy"})
#: CR-073 D2b: a harassment card sits on the attacker's side, the opponent of the node's player (the player
#: who lost the workers); the node's player itself is unchanged.
OPPONENT_SIDE = frozenset({"Harrasment"})
