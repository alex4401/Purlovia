from typing import Any, Dict, List

from ue.asset import UAsset

from .structs import *

__all__ = ['segregate_container_additions']


def _merge_changes(d):
    vs = []
    for _, changes in d.items():
        if len(changes) == 1:
            vs.append(changes[0])
            continue

        v = changes.pop(0)
        # Make sure 'entries' and 'limits' are initialised.
        if 'entries' not in v:
            v['entries'] = []
        if 'limits' not in v:
            v['limits'] = []

        # Concat data arrays
        for extra in changes:
            if 'entries' in extra:
                v['entries'] += extra['entries']
            if 'limits' in extra:
                v['limits'] += extra['limits']

        # Remove empty arrays and add the container mod
        if not v['limits']:
            del v['limits']
        if not v['entries']:
            del v['entries']
        vs.append(v)
    return vs


def segregate_container_additions(pgd: UAsset):
    if not pgd.default_export:
        return None

    export_data = pgd.default_export.properties
    d = export_data.get_property('TheNPCSpawnEntriesContainerAdditions', fallback=None)
    if not d:
        return None

    # Extract the addition entries
    change_queues: Dict[str, List[Dict[str, Any]]] = dict()
    for add in d.values:
        add = add.as_dict()
        klass = add['SpawnEntriesContainerClass']
        entries = add['AdditionalNPCSpawnEntries'].values
        limits = add['AdditionalNPCSpawnLimits'].values
        if not klass.value.value or (not entries and not limits):
            continue

        v = dict()
        v['blueprintPath'] = klass
        if entries:
            v['entries'] = [convert_group_entry(entry) for entry in entries]

        if limits:
            v['limits'] = [convert_limit_entry(entry) for entry in limits]

        # Skip if no data
        if 'limits' not in v and 'entries' not in v:
            continue

        # Append to the fragment list
        klass_name = klass.format_for_json()
        if klass_name not in change_queues:
            change_queues[klass_name] = []
        change_queues[klass_name].append(v)

    return _merge_changes(change_queues)
