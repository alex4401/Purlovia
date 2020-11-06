from typing import Any, Dict, List, Set, Tuple

from ue.hierarchy import find_sub_classes

from .frozen_structs import NpcEntry, NpcGroup, NpcSpawnContainer, RandomClassSwapInfo, SpawningData
from .utils import update_npc_group_with_random_replacements

# Random class swap info construction


def construct_uniform_swap_info(data: Dict[str, Any], version: int) -> Dict[str, RandomClassSwapInfo]:
    out = dict()

    for entry in data:
        from_bp = entry['from']
        to_bps = entry['to']
        weights = entry['weights']

        # Make sure the length of weights is the same as
        # the length of to_bps.
        wt = len(to_bps) - len(weights)
        if wt > 0:
            for _ in range(wt):
                weights.append(1)
        elif wt < 0:
            weights = weights[:len(to_bps)]
        weight_sum = sum(weights)

        # Construct the object
        info = RandomClassSwapInfo(
            to=to_bps,
            chances=[weight / weight_sum for weight in weights],
            during=entry.get('during', 'None'),
        )

        # Associate the info in lookup to the class.
        out[from_bp] = info
        if not entry.get('exact', False):
            # ... and its descendants.
            for child in find_sub_classes(from_bp):
                out[child] = info

    return out


# NPC Group construction


def construct_uniform_npc_group(data: Dict[str, Any], version: int) -> NpcGroup:
    out = NpcGroup(
        name=data['name'],
        weight=data['weight'],
        species=list(),
    )

    # NPC entries are zipped into individual objects
    # beginning with version 4.
    if version >= 4:
        # Structures are compatible.
        for npc in data['species']:
            chance = npc['chance']
            chance = min(max(0, chance), 1)
            entry = NpcEntry(chance=chance, bp=npc['bp'])
            out.species.append(entry)
    else:
        # Each entry is split between three value lists.
        for index, npc_class in enumerate(data['classes']):
            chance = data['classWeights'].get(index, 1)
            chance = min(max(0, chance), 1)
            entry = NpcEntry(
                chance=chance,
                bp=npc_class,
            )
            out.species.append(entry)

    # Apply random class replacements if any are given.
    random_data = data.get('classSwaps', None)
    if random_data:
        lookup = construct_uniform_swap_info(random_data, version)
        update_npc_group_with_random_replacements(lookup)

    return out


# NpcSpawnContainer construction


def make_uniform_container(data: Dict[str, Any], version: int) -> Tuple[str, NpcSpawnContainer]:
    # Access the blueprint path of the container.
    # Starting with version 4, this is now stored in `bp`
    # instead of `blueprintPath`.
    if version >= 4:
        bp = data['bp']
    else:
        bp = data['blueprintPath']

    # Construct a data object.
    container = NpcSpawnContainer(
        maxNPCNumberMultiplier=data['maxNPCNumberMultiplier'],
        groups=[],
    )

    # Convert all NPC Groups
    for group_data in data.get('entries', []):
        group = construct_uniform_npc_group(group_data)
        container.groups.append(group)

    return bp, container


# SpawningData construction


def make_uniform_data_object(filedata: Dict[str, Any]) -> SpawningData:
    version = int(filedata['format'])
    out = SpawningData(groups=dict(), extra_groups=dict(), replacements=list(), remaps=dict())

    # Load NPC spawning group container data
    for container_data in filedata['spawngroups']:
        bp, container = make_uniform_container(container_data)
        out.groups[bp] = container

    # Load random class replacement data
    swap_data = filedata.get('classSwaps', None)
    if swap_data:
        filedata.replacements = construct_uniform_swap_info(swap_data)

    # Add external group additions from mods
    extra_groups = filedata.get('externalGroupChanges', None)
    if extra_groups:
        for extra_data in extra_groups:
            bp = extra_data['bp']
            groups_data = extra_data.get('entries', [])
            results = list()
            for group in groups_data:
                results.append(construct_uniform_npc_group(group, version))
            out.extra_groups[bp] = results

    # Load static class replacement data
    if version >= 4:
        for remap in filedata.get('dinoRemaps', list()):
            out.remaps[remap['from']] = remap['to']

    return out


def get_creatures_spawned_by_mod(data: SpawningData) -> Set[str]:
    '''Gathers '''
    results = set()

    for containers in data.groups.values():
        for container in containers:
            for group in container.groups:
                for npc in group.species:
                    results.add(npc.bp)

    for group in data.extra_groups.values():
        for npc in group.species:
            results.add(npc.bp)

    for swapinfo in data.replacements.values():
        results.update(swapinfo.to)

    return results
