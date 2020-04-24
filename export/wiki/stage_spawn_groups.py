from pathlib import Path, PurePosixPath
from typing import Any, Dict, Optional, cast

from automate.hierarchy_exporter import JsonHierarchyExportStage
from ue.asset import UAsset
from ue.proxy import UEProxyStructure
from ue.utils import clean_double as cd

from .spawn_groups.additions import segregate_container_additions
from .spawn_groups.remaps import convert_npc_remaps
from .spawn_groups.structs import *
from .spawn_groups.swaps import convert_class_swaps
from .types import NPCSpawnEntriesContainer

__all__ = [
    'SpawnGroupStage',
]


class SpawnGroupStage(JsonHierarchyExportStage):
    def get_name(self) -> str:
        return 'spawn_groups'

    def get_field(self) -> str:
        return 'spawngroups'

    def get_use_pretty(self) -> bool:
        return bool(self.manager.config.export_wiki.PrettyJson)

    def get_format_version(self):
        return '4'

    def get_ue_type(self):
        return NPCSpawnEntriesContainer.get_ue_type()

    def get_post_data(self, modid: Optional[str]) -> Optional[Dict[str, Any]]:
        if modid:
            mod_data = self.manager.arkman.getModData(modid)
            assert mod_data

            package = mod_data.get('package', None)
            if package:
                pgd_asset = self.manager.loader[package]
                return self._get_pgd_data(pgd_asset)
        else:
            pgd_asset = self.manager.loader['/Game/PrimalEarth/CoreBlueprints/BASE_PrimalGameData_BP']
            return self._get_pgd_data(pgd_asset)

        return None

    def _get_pgd_data(self, pgd: UAsset) -> Dict[str, Any]:
        v = dict()

        class_swaps = convert_class_swaps(pgd)
        ext_group_changes = segregate_container_additions(pgd)
        npc_remaps = convert_npc_remaps(pgd)

        if class_swaps:
            v['classSwaps'] = class_swaps
        if ext_group_changes:
            v['externalGroupChanges'] = ext_group_changes
        if npc_remaps:
            v['dinoRemaps'] = npc_remaps

        return v

    def extract(self, proxy: UEProxyStructure) -> Any:
        container: NPCSpawnEntriesContainer = cast(NPCSpawnEntriesContainer, proxy)

        # Export basic values
        values: Dict[str, Any] = dict()
        values['blueprintPath'] = container.get_source().fullname
        values['maxNPCNumberMultiplier'] = container.MaxDesiredNumEnemiesMultiplier[0]

        # Export NPC class entries
        if container.has_override('NPCSpawnEntries'):
            values['entries'] = [convert_group_entry(entry) for entry in container.NPCSpawnEntries[0].values]

        # Export class spawn limits
        if container.has_override('NPCSpawnLimits'):
            values['limits'] = [convert_limit_entry(entry) for entry in container.NPCSpawnLimits[0].values]

        return values
