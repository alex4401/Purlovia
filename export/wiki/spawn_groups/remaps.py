from ue.asset import UAsset

__all__ = ['convert_npc_remaps']


def convert_npc_remaps(pgd: UAsset):
    assert pgd.default_export
    all_values = []
    export_data = pgd.default_export.properties
    d = export_data.get_property('Remap_NPC', fallback=None)
    if not d:
        return None

    for entry in d.values:
        de = entry.as_dict()
        v = {
            'from': de['FromClass'],
            'to': de['ToClass'],
        }
        all_values.append(v)

    return all_values
