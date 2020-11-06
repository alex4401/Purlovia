from typing import Dict

from export.maps.frozen_structs import NpcEntry, NpcGroup, NpcSpawnContainer, RandomClassSwapInfo


def update_npc_group_with_random_replacements(group: NpcGroup, lookup: Dict[str, RandomClassSwapInfo]):
    kept = list()
    added = list()

    for npc in group.species:
        if not npc.bp:
            kept.append(npc)
            continue

        info = lookup.get(npc.bp, None)
        if not info:
            kept.append(npc)
            continue

        for index, target_bp in enumerate(info.to):
            new = NpcEntry(
                chance=info.weights[index] * npc.chance,
                bp=target_bp,
            )
            added.append(new)

    group.species = kept + added


def update_container_with_random_replacements(container: NpcSpawnContainer, lookup: Dict[str, RandomClassSwapInfo]):
    for group in container.entries:
        update_npc_group_with_random_replacements(group, lookup)
