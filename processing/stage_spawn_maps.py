import shutil
from logging import NullHandler, getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional

from ark.overrides import get_overrides_for_map
from processing.common import SVGBoundaries, remove_unicode_control_chars

from .spawn_maps.game_mod import merge_game_mod_groups
from .spawn_maps.rarity import apply_ideal_grouplevel_swaps, \
    calculate_blueprint_freqs, fix_up_groups, make_random_class_weights_dict
from .spawn_maps.species import determine_tamability, generate_dino_mappings
from .spawn_maps.svg import generate_svg_map
from .stage_base import ProcessingStage

logger = getLogger(__name__)
logger.addHandler(NullHandler())

__all__ = [
    'ProcessSpawnMapsStage',
]


class ProcessSpawnMapsStage(ProcessingStage):
    def get_skip(self) -> bool:
        return not self.manager.config.processing.ProcessSpawns

    def extract_core(self, _: Path):
        # Find data of maps with NPC spawns
        map_set: List[Path] = [path.parent for path in self.wiki_path.glob('*/npc_spawns.json')]

        # Load ASB and spawning group data
        data_asb = self._load_asb(None)
        data_groups, data_swaps = self._get_spawning_groups(None)
        if not data_asb or not data_groups:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        for map_data_path in map_set:
            self._map_process_data(map_data_path, data_asb, data_groups, None, data_swaps)

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

        # Do all the insanity now and fix up the groups.
        fix_up_groups(data)
        apply_ideal_grouplevel_swaps(data)
        # Global class swaps will be applied during freq calculations.

        return data, swaps

    def _map_mod_generate_svgs(self, modid: str, mod_name: str):
        # Find data of maps with NPC spawns
        root_wiki_mod_dir = Path(self.wiki_path / f'{modid}-{mod_name}')
        map_set: List[Path] = [path.parent for path in root_wiki_mod_dir.glob('*/npc_spawns.json')]

        # Load and merge ASB data
        data_asb_core = self._load_asb(None)
        data_asb_mod = self._load_asb(modid)
        if not data_asb_core or not data_asb_mod:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return
        data_asb_mod['species'] += data_asb_core['species']

        # Load and merge spawning group data
        data_groups, data_swaps = self._get_spawning_groups(modid)
        if not data_groups:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        for map_data_path in map_set:
            self._map_process_data(map_data_path, data_asb_mod, data_groups, modid, data_swaps)

    def _game_mod_generate_svgs(self, modid: str, _mod_name: str):
        # Find data of core maps with NPC spawns
        map_set: List[Path] = [path.parent for path in self.wiki_path.glob('*/npc_spawns.json')]

        # Load ASB and spawning group data
        data_asb = self._load_asb(modid)
        data_groups, data_swaps = self._get_spawning_groups(modid, is_game_mod=True)
        if not data_asb or not data_groups:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        for map_data_path in map_set:
            self._map_process_data(map_data_path, data_asb, data_groups, modid, data_swaps)

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

    def _map_process_data(self,
                          data_path: Path,
                          asb: Dict[str, Any],
                          spawngroups: Dict[str, Any],
                          modid: Optional[str],
                          global_swaps: Optional[List] = None):
        map_name = data_path.name
        logger.info(f'Processing data of map: {map_name}')

        # Load exported data
        data_map_settings = self.load_json_file(data_path / 'world_settings.json')
        data_map_spawns = self.load_json_file(data_path / 'npc_spawns.json')
        if not data_map_settings or not data_map_spawns:
            logger.debug(f'Data required by the processor is missing or invalid. Skipping.')
            return

        # Initialize bound structure for this map
        bounds = _get_svg_bounds_for_map(data_map_settings['persistentLevel'])

        # Generate mapping table (blueprint path to name)
        species = generate_dino_mappings(asb)

        # Get world-level random dino class swaps
        map_swaps = data_map_settings['worldSettings'].get('randomNPCClassWeights', [])
        all_swaps = [
            make_random_class_weights_dict(map_swaps),
        ]
        if 'onlyEventGlobalSwaps' not in data_map_settings['worldSettings']:
            # Include global swaps as the map allows them
            all_swaps.append(make_random_class_weights_dict(global_swaps))
        # TODO: Expand the swaps ahead of time

        # Determine base output path
        output_path = self._get_svg_output_path(data_path, map_name, modid)
        # Remove existing directory
        if output_path.is_dir():
            shutil.rmtree(output_path)

        # Generate maps for every species
        for export_class, blueprints in species.items():
            untameable = not determine_tamability(asb, export_class)

            # The rarity is arbitrarily divided in 6 groups from "very rare" (0) to "very common" (5)
            freqs = calculate_blueprint_freqs(spawngroups, all_swaps, blueprints)

            svg = generate_svg_map(bounds, freqs, data_map_spawns, untameable)
            if svg:
                filepath = output_path / self._make_filename_for_export(export_class)
                self.save_raw_file(svg, filepath)

    def _make_filename_for_export(self, blueprint_path):
        clean_bp_name = blueprint_path.rsplit('.')[-1]
        if clean_bp_name.endswith('_C'):
            clean_bp_name = clean_bp_name[:-2]
        clean_bp_name = remove_unicode_control_chars(clean_bp_name)

        modid = self.manager.loader.get_mod_id(blueprint_path)
        if modid:
            clean_bp_name += f'_({modid})'

        return f'Spawning_{clean_bp_name}.svg'


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
