from export.wiki.maps.models import WeighedClassSwap
from ue.utils import sanitise_output

__all__ = [
    'convert_single_class_swap',
    'convert_group_entry',
    'convert_limit_entry',
]


def convert_single_class_swap(d):
    result = WeighedClassSwap(from_class=sanitise_output(d['FromClass']),
                              exact=bool(d.get('bExactMatch', True)),
                              to=sanitise_output(d['ToClasses']),
                              weights=d['Weights'].values)

    if d['ActiveEvent'] and d['ActiveEvent'].value and d['ActiveEvent'].value.value:
        # Assigning "None" here is safe as it is the field default and therefore omitted
        result.during = str(d['ActiveEvent'])

    return result


def convert_group_entry(struct):
    d = struct.as_dict()

    v = dict()
    v['name'] = d['AnEntryName']
    v['weight'] = d['EntryWeight']
    v['classes'] = d['NPCsToSpawn']
    v['spawnOffsets'] = d['NPCsSpawnOffsets']
    v['classWeights'] = d['NPCsToSpawnPercentageChance']

    d_swaps = d['NPCRandomSpawnClassWeights'].values
    if d_swaps:
        v['classSwaps'] = [convert_single_class_swap(entry.as_dict()) for entry in d_swaps]

    return v


def convert_limit_entry(struct):
    d = struct.as_dict()

    v = dict()
    v['class'] = d['NPCClass']
    v['desiredNumberMult'] = d['MaxPercentageOfDesiredNumToAllow']

    return v
