import json
from abc import ABCMeta
from pathlib import Path
from typing import Any, List, Optional

from automate.exporter import ExportManager, ExportRoot, ExportStage
from utils.log import get_logger

logger = get_logger(__name__)

__all__ = [
    'ProcessingStage',
]


class ProcessingStage(ExportStage, metaclass=ABCMeta):  # pylint: disable=abstract-method
    asb_path: Path
    wiki_path: Path
    output_path: Path

    def initialise(self, manager: ExportManager, root: ExportRoot):
        super().initialise(manager, root)

        self.output_path = self.manager.config.settings.OutputPath / self.root.get_relative_path()
        self.asb_path = self.manager.config.settings.OutputPath / self.manager.config.export_asb.PublishSubDir
        self.wiki_path = self.manager.config.settings.OutputPath / self.manager.config.export_wiki.PublishSubDir

    def get_mod_subroot_name(self, modid: str) -> str:
        mod_data = self.manager.arkman.getModData(modid)
        assert mod_data
        return f'{modid}-{mod_data["name"]}'

    def load_json_file(self, path: Path) -> Any:
        '''Attempts to load a JSON file. Returns None on error.'''
        try:
            with open(path, 'rt', encoding='utf-8') as fp:
                data = json.load(fp)
                return data
        except OSError:
            return None

    def load_asb(self, modid: Optional[str]):
        if modid:
            return self.load_json_file(self.asb_path / f'{self.get_mod_subroot_name(modid)}.json')
        return self.load_json_file(self.asb_path / 'values.json')

    def load_spawning_groups(self, modid: Optional[str]):
        if modid:
            return self.load_json_file(self.wiki_path / self.get_mod_subroot_name(modid) / 'spawn_groups.json')
        return self.load_json_file(self.wiki_path / 'spawn_groups.json')

    def save_raw_file(self, content: str, path: Path):
        '''Writes a string to a UTF-8 encoded file.'''
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'wt', newline='\n', encoding='utf-8') as f:
            f.write(content)

    def find_maps(self, path: Path, keyword='world_settings') -> List[Path]:
        '''Returns a list of maps in specific path of the output directory.'''
        return [p.parent.relative_to(self.wiki_path) for p in path.glob(f'*/{keyword}.json')]

    def find_official_maps(self, only_core=False, keyword='world_settings') -> List[Path]:
        '''Returns a list of official maps in the output directory.'''
        results = self.find_maps(self.wiki_path, keyword)

        if not only_core:
            for separate_id in self.manager.config.settings.SeparateOfficialMods:
                mod_data = self.manager.arkman.getModData(separate_id)
                assert mod_data
                tag = mod_data['name']

                mod_path = self.wiki_path / f'{separate_id}-{tag}'
                results += self.find_maps(mod_path, keyword)

        return results
