def merge_game_mod_groups(core_groups, changeset):
    # Create a dictionary for quicker look-ups of core groups
    groups = dict()
    for group in core_groups:
        groups[group['blueprintPath']] = group

    # Merge with the change-set
    for change in changeset:
        blueprint_path = change['blueprintPath']
        if blueprint_path not in groups:
            continue
        orig_group = groups[blueprint_path]

        if 'entries' in change:
            if 'entries' in orig_group:
                orig_group['entries'] += change['entries']
            else:
                orig_group['entries'] = change['entries']

        if 'limits' in change:
            if 'limits' in orig_group:
                orig_group['limits'] += change['limits']
            else:
                orig_group['limits'] = change['limits']


def apply_remaps(groups, remaps):
    if not remaps:
        return
    fromto = {e['from']: e['to'] for e in remaps}

    for group in groups:
        for entry in group['entries']:
            for index, klass in enumerate(entry['classes']):
                new_klass = fromto.get(klass, None)
                entry['classes'][index] = new_klass or klass
