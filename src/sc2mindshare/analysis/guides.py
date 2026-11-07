"""Build order guides: the shipped library, loading and the guide check (CR-035, AC8, AC9, AC11; P0-1).

The five guides ship as package data in ``config/guides/`` (D4a): three Liquipedia ZvP guides (CC BY-SA 3.0, their
attribution in the file) and two PvZ drafts the team wrote (``source.kind: project``, shown as team drafts).

``check(data)`` applies P0-1 §7's rules V1 and V3-V11 to one file's JSON and returns the problems, each with the
player-facing message CR-035 lists for its rule (P0-1 §7 for V1, V4 and V5; Iris's O-6 table for the others, which
supersedes P0-1 §7's wording: the player never reads "benchmark"). ``check_library`` adds V2 (unique ids).
``load(path)`` reads and checks one file and raises ``GuideError`` with the first problem.
"""

from __future__ import annotations

import datetime
import json
import re
from collections.abc import Iterable, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any

from sc2mindshare.domain.guides import Guide, GuideStep

RACES = ("Zerg", "Protoss", "Terran")
KINDS = ("worker", "unit", "building", "morph", "upgrade")
SOURCE_KINDS = ("liquipedia", "sc2planner", "project", "replay", "spawningtool-link")
#: P0-1 §5: the fields each kind of source must carry.
SOURCE_FIELDS = {
    "liquipedia": ("title", "url", "revision", "retrieved", "licence", "attribution", "changes"),
    "sc2planner": ("planner_url", "author", "created", "licence"),
    "project": ("author", "created", "licence"),
    "replay": ("replay", "player", "extracted_by", "licence"),
    "spawningtool-link": ("title", "url"),
}
#: The latest reach a guide may have (V11).
MAX_HORIZON = 15 * 60
DEFAULT_HORIZON = 6 * 60  # D8a

_CLOCK = re.compile(r"(\d{1,2}):([0-5]\d)")
_ID = re.compile(r"[a-z0-9-]+")
_PATCH = re.compile(r"\d+\.\d+\.\d+")

_WEAPONS = {f"{race}{kind}Level{n}" for race, kinds in (
    ("Zerg", ("MeleeWeapons", "MissileWeapons", "FlyerWeapons", "GroundArmors", "FlyerArmors")),
    ("Protoss", ("GroundWeapons", "GroundArmors", "AirWeapons", "AirArmors", "Shields")),
    ("Terran", ("InfantryWeapons", "InfantryArmors", "VehicleWeapons", "ShipWeapons", "VehicleAndShipArmors")),
) for kind in kinds for n in (1, 2, 3)}  # fmt: skip


def _ids(text: str) -> frozenset[str]:
    return frozenset(text.split())


#: P0-2 §6's canonical ids per race (the internal ids the replay's units, buildings and upgrades carry), for V4.
ITEMS: dict[str, frozenset[str]] = {
    "Zerg": _ids(
        "Drone Overlord Overseer Zergling Queen Roach Ravager Baneling Hydralisk LurkerMP Infestor "
        "SwarmHostMP Ultralisk Mutalisk Corruptor BroodLord Viper Hatchery Lair Hive Extractor "
        "SpawningPool EvolutionChamber RoachWarren BanelingNest HydraliskDen LurkerDenMP InfestationPit "
        "Spire GreaterSpire NydusNetwork UltraliskCavern SpineCrawler SporeCrawler zerglingmovementspeed "
        "zerglingattackspeed overlordspeed overlordtransport GlialReconstitution TunnelingClaws "
        "CentrificalHooks EvolveMuscularAugments EvolveGroovedSpines Burrow ChitinousPlating "
        "AnabolicSynthesis LurkerRange DiggingClaws NeuralParasite InfestorEnergyUpgrade MicrobialShroud"
    )
    | {w for w in _WEAPONS if w.startswith("Zerg")},
    "Protoss": _ids(
        "Probe Zealot Stalker Sentry Adept HighTemplar DarkTemplar Archon Observer WarpPrism Immortal "
        "Colossus Disruptor Phoenix Oracle VoidRay Tempest Carrier Mothership Nexus Pylon Assimilator "
        "Gateway WarpGate Forge CyberneticsCore PhotonCannon ShieldBattery TwilightCouncil "
        "RoboticsFacility Stargate TemplarArchive DarkShrine RoboticsBay FleetBeacon WarpGateResearch "
        "Charge BlinkTech AdeptPiercingAttack PsiStormTech DarkTemplarBlinkUpgrade ExtendedThermalLance "
        "ObserverGraviticBooster GraviticDrive PhoenixRangeUpgrade VoidRaySpeedUpgrade "
        "TempestGroundAttackUpgrade"
    )
    | {w for w in _WEAPONS if w.startswith("Protoss")},
    "Terran": _ids(
        "SCV Marine Marauder Reaper Ghost Hellion HellionTank WidowMine SiegeTank Cyclone Thor "
        "VikingFighter Medivac Liberator Raven Banshee Battlecruiser CommandCenter OrbitalCommand "
        "PlanetaryFortress SupplyDepot Refinery Barracks Factory Starport EngineeringBay Armory Bunker "
        "MissileTurret SensorTower GhostAcademy FusionCore BarracksReactor BarracksTechLab FactoryReactor "
        "FactoryTechLab StarportReactor StarportTechLab Stimpack ShieldWall PunisherGrenades "
        "HighCapacityBarrels DrillClaws BansheeCloak BansheeSpeed PersonalCloaking HiSecAutoTracking "
        "TerranBuildingArmor SmartServos MedivacIncreaseSpeedBoost MedivacCaduceusReactor "
        "RavenCorvidReactor BattlecruiserEnableSpecializations CycloneLockOnDamageUpgrade"
    )
    | {w for w in _WEAPONS if w.startswith("Terran")},
}
#: What every player starts with (P0-2 §3.1): never a step (V8).
WORKERS = {"Zerg": "Drone", "Protoss": "Probe", "Terran": "SCV"}
TOWN_HALLS = {"Zerg": "Hatchery", "Protoss": "Nexus", "Terran": "CommandCenter"}


class GuideError(ValueError):
    """A guide file that cannot be used, with the player-facing message (AC10, AC11)."""


def clock(text: str) -> int:
    """``m:ss`` as whole seconds."""
    match = _CLOCK.fullmatch(text)
    if match is None:
        raise ValueError(f"not a m:ss time: {text!r}")
    return int(match.group(1)) * 60 + int(match.group(2))


def _is_clock(value: Any) -> bool:
    return isinstance(value, str) and _CLOCK.fullmatch(value) is not None


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_date(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


#: V1: the top-level fields, their check and the type named in the message.
_TOP: tuple[tuple[str, bool, Any, str], ...] = (
    ("format_version", True, lambda v: v == "1", '"1"'),
    ("id", True, lambda v: isinstance(v, str) and _ID.fullmatch(v) is not None, "lower-case letters, digits and -"),
    ("name", True, lambda v: isinstance(v, str) and v != "", "text"),
    ("race", True, lambda v: v in RACES, "Zerg, Protoss or Terran"),
    ("vs", True, lambda v: v in (*RACES, "Any"), "Zerg, Protoss, Terran or Any"),
    ("era", True, lambda v: isinstance(v, str), "text"),
    ("patch", True, lambda v: v is None or (isinstance(v, str) and _PATCH.fullmatch(v) is not None), "a patch or null"),
    ("as_of", True, _is_date, "a date"),
    ("horizon", False, _is_clock, "m:ss"),
    ("source", True, lambda v: isinstance(v, dict) and v.get("kind") in SOURCE_KINDS, "a source"),
    ("steps", True, lambda v: isinstance(v, list) and all(isinstance(s, dict) for s in v), "a list of steps"),
    ("notes", False, lambda v: isinstance(v, str), "text"),
    ("worker_targets", False, lambda v: isinstance(v, list), "a list"),
)
#: V1 for a step's fields.
_STEP: tuple[tuple[str, bool, Any, str], ...] = (
    ("item", True, lambda v: isinstance(v, str) and v != "", "text"),
    ("text", True, lambda v: isinstance(v, str), "text"),
    ("kind", True, lambda v: v in KINDS, "worker, unit, building, morph or upgrade"),
    ("count", False, lambda v: _is_int(v) and v >= 1, "a whole number from 1"),
    ("supply", False, _is_int, "a whole number"),
    (
        "supply_range",
        False,
        lambda v: isinstance(v, list) and len(v) == 2 and all(_is_int(x) for x in v),
        "two whole numbers",
    ),
    ("time", False, _is_clock, "m:ss"),
    ("time_interval", False, lambda v: isinstance(v, list) and len(v) == 2 and all(_is_clock(x) for x in v), "two m:ss"),
    ("time_source", False, lambda v: v in ("source", "simulated"), "source or simulated"),
    ("trigger", False, lambda v: isinstance(v, str) and v != "", "text"),
    ("alternatives", False, lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v), "a list of items"),
    ("key", False, lambda v: isinstance(v, bool), "true or false"),
    ("optional", False, lambda v: isinstance(v, bool), "true or false"),
    ("note", False, lambda v: isinstance(v, str), "text"),
)


def _fields(data: dict[str, Any], spec: Sequence[tuple[str, bool, Any, str]], prefix: str) -> list[str]:
    problems = []
    for name, required, ok, kind in spec:
        if name not in data:
            if required:
                problems.append(f"{prefix}`{name}` is missing")
        elif not ok(data[name]):
            problems.append(f"{prefix}`{name}` must be {kind}")
    return problems


def _step_problems(n: int, step: dict[str, Any], race: str) -> list[str]:
    """V1 (a step's fields), V4, V5, V6, V8 and V9 for step ``n``."""
    problems = _fields(step, _STEP, f"Step {n}: ")
    if problems:
        return problems
    item = step["item"]
    if any(i not in ITEMS.get(race, frozenset()) for i in (item, *step.get("alternatives", []))):  # V4
        bad = next(i for i in (item, *step.get("alternatives", [])) if i not in ITEMS.get(race, frozenset()))
        return [f"Step {n}: unknown item `{bad}`"]
    supply_range = step.get("supply_range")
    interval = step.get("time_interval")
    descending = (supply_range is not None and supply_range[0] > supply_range[1]) or (
        interval is not None and clock(interval[0]) > clock(interval[1])
    )
    given = [k for k in ("supply", "supply_range", "time", "time_interval", "trigger") if k in step]
    if (
        not given or ("supply" in step and "supply_range" in step) or ("time" in step and "time_interval" in step) or descending
    ):  # V5
        return [f"Step {n}: give one of supply, time or trigger"]
    supplies = [step["supply"]] if "supply" in step else list(supply_range or [])
    if any(s < 12 for s in supplies):  # V6
        return [f"Step {n}: supply below 12; is this a build order from before Legacy of the Void?"]
    starting = item == TOWN_HALLS.get(race) or item == WORKERS.get(race) or (race == "Zerg" and item == "Overlord")
    at_zero = step.get("time") == "0:00" or (interval is not None and clock(interval[0]) == 0)
    if starting and (at_zero or (item == WORKERS.get(race) and step.get("count", 1) >= 12)):  # V8
        return [f"Step {n}: the units you start with (workers, town hall, first Overlord) are not steps"]
    if ("time" in step or "time_interval" in step) and "time_source" not in step:  # V9
        return [f"Step {n}: has a time but no `time_source`"]
    return []


def _start_second(step: dict[str, Any]) -> int | None:
    if "time" in step:
        return clock(step["time"])
    if "time_interval" in step:
        return clock(step["time_interval"][0])
    return None


def check(data: Any) -> list[str]:
    """The problems of one guide file's JSON (V1, V3-V11), each with its player-facing message; [] if none."""
    if not isinstance(data, dict):
        return ["the file must hold one build order guide (a JSON object)"]
    problems = _fields(data, _TOP, "")
    if problems:
        return problems
    if data["era"] != "LotV":  # V3
        return ["Only Legacy of the Void build orders are supported"]
    source = data["source"]
    kind = source["kind"]
    steps = data["steps"]
    if kind == "spawningtool-link" and steps:  # V10
        return ["Spawning Tool build orders can only be linked, not copied in"]
    missing = [f for f in SOURCE_FIELDS[kind] if f not in source]
    if missing:
        return [f"`{missing[0]}` is required for a {kind} source"]
    if kind != "spawningtool-link" and not steps:
        return [f"`steps` must list at least one step for a {kind} source"]
    for n, step in enumerate(steps, start=1):
        problems += _step_problems(n, step, data["race"])
    if problems:
        return problems
    previous: int | None = None
    for n, step in enumerate(steps, start=1):  # V7
        second = _start_second(step)
        if second is None:
            continue
        if previous is not None and second < previous:
            return [f"Step {n}: its time is earlier than the step before it"]
        previous = second
    if "horizon" in data:  # V11
        horizon = clock(data["horizon"])
        first = _start_second(steps[0]) if steps else None
        if horizon > MAX_HORIZON or horizon <= 0 or (first is not None and horizon <= first):
            return ["`horizon` (how far into the game it goes) must be after the first step and no later than 15:00"]
    return []


def check_library(guides: Iterable[Guide]) -> list[str]:
    """V2: every id once in the library."""
    seen: set[str] = set()
    problems = []
    for g in guides:
        if g.id in seen:
            problems.append(f"Two build order guides have the same id `{g.id}`")
        seen.add(g.id)
    return problems


def _step(n: int, s: dict[str, Any]) -> GuideStep:
    interval = s.get("time_interval")
    supply_range = s.get("supply_range")
    return GuideStep(
        number=n,
        item=s["item"],
        text=s["text"],
        kind=s["kind"],
        count=s.get("count", 1),
        supply=s.get("supply"),
        supply_range=(supply_range[0], supply_range[1]) if supply_range else None,
        time=clock(s["time"]) if "time" in s else None,
        time_interval=(clock(interval[0]), clock(interval[1])) if interval else None,
        time_source=s.get("time_source"),
        trigger=s.get("trigger"),
        alternatives=tuple(s.get("alternatives", ())),
        key=s.get("key", False),
        optional=s.get("optional", False),
        note=s.get("note"),
    )


def parse(data: Any, file: str = "") -> Guide:
    """A checked guide from one file's JSON; ``GuideError`` with the first problem otherwise."""
    problems = check(data)
    if problems:
        raise GuideError(problems[0])
    return Guide(
        id=data["id"],
        name=data["name"],
        race=data["race"],
        vs=data["vs"],
        era=data["era"],
        patch=data["patch"],
        as_of=data["as_of"],
        horizon=clock(data["horizon"]) if "horizon" in data else DEFAULT_HORIZON,
        source=dict(data["source"]),
        steps=tuple(_step(n, s) for n, s in enumerate(data["steps"], start=1)),
        file=file,
    )


def load(path: Path) -> Guide:
    """One guide file, read and checked. A file that is not JSON is unreadable too."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GuideError("it is not a JSON file") from exc
    return parse(data, path.name)


def library() -> tuple[Guide, ...]:
    """The shipped guides, in file-name order, checked (V1-V11, V2 across them)."""
    root = files("sc2mindshare") / "config" / "guides"
    guides = tuple(
        parse(json.loads(p.read_text(encoding="utf-8")), p.name)
        for p in sorted(root.iterdir(), key=lambda p: p.name)
        if p.name.endswith(".benchmark.json")
    )
    problems = check_library(guides)
    if problems:
        raise GuideError(problems[0])
    return guides
