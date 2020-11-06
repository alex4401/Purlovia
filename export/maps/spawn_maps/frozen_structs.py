from dataclasses import dataclass
from typing import Dict, List, Optional

__all__ = [
    'NpcEntry',
    'NpcGroup',
    'NpcSpawnContainer',
    'RandomClassSwapInfo',
    'SpawningData',
]

# These structures may have a different field set compared to
# the export, as they're targeted at spawning maps and frozen
# in time.


@dataclass
class RandomClassSwapInfo:
    to: List[Optional[str]]
    chances: List[float]
    during: str = 'None'


@dataclass
class NpcEntry:
    chance: float
    bp: Optional[str]


@dataclass
class NpcGroup:
    name: str
    weight: float
    species: List[NpcEntry]


@dataclass
class NpcSpawnContainer:
    maxNPCNumberMultiplier: float
    groups: List[NpcGroup]


@dataclass
class SpawningData:
    groups: Dict[str, List[NpcSpawnContainer]]
    extra_groups: Dict[str, List[NpcGroup]]
    replacements: Dict[str, RandomClassSwapInfo]
    remaps: Dict[str, str]
