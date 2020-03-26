VARIANTS = [
    'Rare',
    #    'Lunar',
    #    'Snow',
    #    'Volcano',
    #    'Ocean',
    #    'Bog',
]


def get_name(asb, blueprint_path):
    for species in asb['species']:
        if species['blueprintPath'] != blueprint_path[:-2]:
            continue

        name = species['name']

        if 'variants' in species:
            for variant in reversed(VARIANTS):
                if variant in species['variants']:
                    name = f'{variant} {name}'

        return name

    raise ValueError(f'{blueprint_path} could not be found in ASB...?')


def b(v):
    return 1 if v else 0


def run(spawns, groups, data):
    # Group managers by group container asset
    manager_lookup = dict()
    for manager in spawns:
        group = manager['spawnGroup']
        if group not in manager_lookup:
            manager_lookup[group] = list()
        manager_lookup[group].append(manager)

    # Group groups by asset name
    group_lookup = dict()
    for group in groups:
        assetname = group['blueprintPath']
        group_lookup[assetname] = group

    # Generate output
    v0 = []
    for group_name, managers in manager_lookup.items():
        if group_name not in group_lookup:
            continue
        group = group_lookup[group_name]

        v1 = dict()
        # v1['n']: str - name
        v1['n'] = group_name[group_name.rfind('.') + 1:]
        v1['n'] = v1['n'][:-2]

        # v1['e']: list - groups
        v1['e'] = list()
        entry_weight_sum = sum(entry['weight'] for entry in group['entries'])
        for entry in group['entries']:
            v2 = dict()

            # v2['n']: str - group name
            v2['n'] = entry['name']

            # v2['c']: float - chance
            v2['c'] = round(entry['weight'] / entry_weight_sum, 2)

            # v2['s']: list - dino entries
            v2['s'] = list()
            for index, dino in enumerate(entry['classes']):
                v3 = dict()

                # v3['n']: str - dino name
                v3['n'] = get_name(data.asb, dino)
                # v3['c']: float - chance
                v3['c'] = round(min(1, entry['classWeights'][index]), 2)

                v2['s'].append(v3)

            v1['e'].append(v2)

        # v1['s']: list - regions
        v1['s'] = list()
        for manager in managers:
            v2 = dict()

            # v2['f']: int - desired number of NPCs to spawn
            v2['f'] = manager['minDesiredNumberOfNPC']

            # v2['t']: ? - seems unused?

            # v2['u']: int : {0,1} - untamability
            v2['u'] = b(manager['forceUntameable'])

            # v2['p']: list - points
            v2['p'] = [get_point(p) for p in manager.get('spawnPoints', [])]
            v2['p'] = list(filter(is_point_valid, v2['p']))

            # v2['l']: list - regions
            v2['l'] = [get_region(p) for p in manager.get('spawnLocations', [])]
            v2['l'] = list(filter(is_region_valid, v2['l']))

            v1['s'].append(v2)

        v0.append(v1)

    return v0


def get_point(d):
    return dict(
        x=round(d['long'], 1),
        y=round(d['lat'], 1),
    )


def get_region(d):
    return dict(
        x1=round(d['start']['long'], 1),
        x2=round(d['end']['long'], 1),
        y1=round(d['start']['lat'], 1),
        y2=round(d['end']['lat'], 1),
    )


def is_region_valid(d):
    d['x1'] = min(100, max(0, d['x1']))
    d['x2'] = min(100, max(0, d['x2']))
    d['y1'] = min(100, max(0, d['y1']))
    d['y2'] = min(100, max(0, d['y2']))

    if d['x2'] < d['x1']:
        d['x1'], d['x2'] = d['x2'], d['x1']

    if d['y2'] < d['y1']:
        d['y1'], d['y2'] = d['y2'], d['y1']

    return (d['x2'] - d['x1']) >= 0 and (d['y2'] - d['y1']) >= 0


def is_point_valid(d):
    d['x'] = min(100, max(0, d['x']))
    d['y'] = min(100, max(0, d['y']))

    return d['x'] >= 0 and d['y'] >= 0
