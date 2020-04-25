import shutil
from collections import namedtuple
from logging import NullHandler, getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional

from ark.overrides import get_overrides_for_map
from automate.jsonutils import save_as_json
from processing.common import SVGBoundaries, remove_unicode_control_chars

from . import fds
from .spawn_maps.game_mod import apply_remaps, merge_game_mod_groups
from .spawn_maps.species import calculate_blueprint_freqs, determine_tamability, generate_dino_mappings
from .spawn_maps.svg import generate_svg_map
from .spawn_maps.swaps import apply_ideal_global_swaps, apply_ideal_grouplevel_swaps, \
    copy_spawn_groups, fix_up_groups, inflate_swap_rules, make_random_class_weights_dict
from .stage_base import ProcessingStage

logger = getLogger(__name__)
logger.addHandler(NullHandler())

__all__ = [
    'ProcessFDSStage',
]

_SpawningData = namedtuple('_SpawningData', ('asb', 'species', 'groups', 'global_swaps'))


class ProcessFDSStage(ProcessingStage):
    def get_name(self) -> str:
        return "fds"

    def extract_core(self, _: Path):
        # Find data of maps with NPC spawns
        maps: List[Path] = [path.parent for path in self.wiki_path.glob('*/npc_spawns.json')]

        # Load ASB and spawning group data
        data_asb = self._load_asb(None)
        data_groups, data_swaps = self._get_spawning_groups(None)
        if not data_asb or not data_groups:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        self._process_all_maps(maps, data_asb, data_groups, data_swaps, None)

    def extract_mod(self, _: Path, modid: str):
        mod_data = self.manager.arkman.getModData(modid)
        assert mod_data
        mod_type = int(mod_data.get('type', 1))
        if mod_type == 1:
            self._game_mod_generate_svgs(modid, mod_data['name'])
        elif mod_type == 2:
            self._map_mod_generate_svgs(modid, mod_data['name'])

    def _load_asb(self, modid: Optional[str]):
        path = self.asb_path
        if modid:
            mod_data = self.manager.arkman.getModData(modid)
            assert mod_data
            path = (path / f'{modid}-{mod_data["name"]}.json')
        else:
            path = (path / 'values.json')
        return self.load_json_file(path)

    def _load_spawning_groups(self, modid: Optional[str]):
        path = self.wiki_path
        if modid:
            mod_data = self.manager.arkman.getModData(modid)
            assert mod_data
            path = (path / f'{modid}-{mod_data["name"]}/spawngroups.json')
        else:
            path = (path / 'spawngroups.json')
        return self.load_json_file(path)

    def _get_spawning_groups(self, modid: Optional[str], is_game_mod: bool = False):
        core_data = self._load_spawning_groups(None)
        if not core_data:
            return None, None
        swaps = core_data['classSwaps']

        # Load mod data and merge it with core
        if modid:
            mod_data = self._load_spawning_groups(modid)
            if not mod_data:
                return None, None
            mod_data['spawngroups'] += core_data['spawngroups']

            if is_game_mod:
                if 'externalGroupChanges' in mod_data:
                    merge_game_mod_groups(mod_data['spawngroups'], mod_data['externalGroupChanges'])
                swaps = mod_data.get('classSwaps', [])

            data = mod_data
        else:
            data = core_data

        # Do all the insanity now and fix up the groups
        fix_up_groups(data['spawngroups'])
        apply_ideal_grouplevel_swaps(data['spawngroups'])
        inflate_swap_rules(swaps)
        apply_remaps(data['spawngroups'], data.get('dinoRemaps', None))
        # Global class swaps will be applied during freq calculations

        return data['spawngroups'], swaps

    def _map_mod_generate_svgs(self, modid: str, mod_name: str):
        # Find data of maps with NPC spawns
        root_wiki_mod_dir = Path(self.wiki_path / f'{modid}-{mod_name}')
        maps: List[Path] = [path.parent for path in root_wiki_mod_dir.glob('*/npc_spawns.json')]

        # Load and merge ASB data
        data_asb_core = self._load_asb(None)
        data_asb_mod = self._load_asb(modid)
        print(type(modid), modid)
        data_asb_mod2 = self._load_asb('1787443195') if modid == '1484748491' else None
        if not data_asb_core:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        if data_asb_mod:
            data_asb_mod['species'] += data_asb_core['species']
        else:
            data_asb_mod = dict(species=data_asb_core['species'])
        if data_asb_mod2:
            data_asb_mod['species'] += data_asb_mod2['species']

        # Load and merge spawning group data
        data_groups, data_swaps = self._get_spawning_groups(modid)
        if not data_groups:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        self._process_all_maps(maps, data_asb_mod, data_groups, data_swaps, modid)

    def _game_mod_generate_svgs(self, modid: str, _mod_name: str):
        # Find data of maps with NPC spawns
        maps: List[Path] = [path.parent for path in self.wiki_path.glob('*/npc_spawns.json')]

        # Load and merge ASB data
        data_asb_core = self._load_asb(None)
        data_asb_mod = self._load_asb(modid)
        if not data_asb_core:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        if data_asb_mod:
            data_asb_mod['species'] += data_asb_core['species']
        else:
            data_asb_mod = dict(species=data_asb_core['species'])

        # Load and merge spawning group data
        data_groups, data_swaps = self._get_spawning_groups(modid, is_game_mod=True)
        if not data_groups:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        self._process_all_maps(maps, data_asb_mod, data_groups, data_swaps, modid)

    def _process_all_maps(self, maps, data_asb, data_groups, data_swaps, modid):
        spawndata = _SpawningData(
            asb=data_asb,
            # Generate species groups
            species=generate_dino_mappings(data_asb),
            # Original spawning groups
            groups=data_groups,
            global_swaps=data_swaps,
        )

        for map_path in maps:
            self._map_process_data(map_path, spawndata, modid)

    def _get_svg_output_path(self, data_path: Path, map_name: str, modid: Optional[str]) -> Path:
        if not modid:
            # Core maps
            #   data/wiki/Map/spawn_maps
            #   or data_path/spawn_maps
            return Path(data_path / 'spawn_maps')

        # Mods
        mod_data = self.manager.arkman.getModData(modid)
        assert mod_data
        mod_type = int(mod_data.get('type', 1))
        if mod_type == 2:
            # Custom maps
            #   data/wiki/Id-Mod/MapName/spawn_maps
            #   or data_path / spawn_maps
            return Path(data_path / 'spawn_maps')

        # mod_type == 1
        # Game mods
        #   data/wiki/Id-Mod/spawn_maps/Map
        #   Data path can't be used as it points at a core map
        return Path(self.wiki_path / f'{modid}-{mod_data["name"]}' / 'spawn_maps' / map_name)

    def _map_process_data(self, data_path: Path, spawndata: _SpawningData, modid: Optional[str]):
        logger.info(f'Processing data of map: {data_path.name}')

        # Determine base output path
        output_path = self._get_svg_output_path(data_path, data_path.name, modid)

        # Load exported data
        data_map_settings = self.load_json_file(data_path / 'world_settings.json')
        data_map_spawns = self.load_json_file(data_path / 'npc_spawns.json')
        if not data_map_settings or not data_map_spawns:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        # Copy spawning groups data
        allows_global_swaps = 'onlyEventGlobalSwaps' not in data_map_settings['worldSettings']
        spawngroups = copy_spawn_groups(spawndata.groups)

        # Apply world-level random dino class swaps
        map_swaps = data_map_settings['worldSettings'].get('randomNPCClassWeights', [])
        inflate_swap_rules(map_swaps)
        apply_ideal_global_swaps(spawngroups, map_swaps)

        # Apply global swaps if allowed
        if allows_global_swaps:
            apply_ideal_global_swaps(spawngroups, spawndata.global_swaps)

        # Generate maps for every species
        data = fds.run(data_map_spawns['spawns'], spawngroups, spawndata)
        if data:
            filepath = output_path / 'fds.json'
            save_as_json(data, filepath, False)


def _get_svg_bounds_for_map(persistent_level: str) -> SVGBoundaries:
    config = get_overrides_for_map(persistent_level, None).svgs
    bounds = SVGBoundaries(
        size=300,
        border_top=config.border_top,
        border_left=config.border_left,
        coord_width=config.border_right - config.border_left,
        coord_height=config.border_bottom - config.border_top,
    )
    return bounds
