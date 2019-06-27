import re
import os.path
import logging
from typing import Union, Tuple
from abc import ABC, abstractmethod
from configparser import ConfigParser
from pathlib import Path, PurePosixPath

from .stream import MemoryStream
from .asset import UAsset, ImportTableItem, ExportTableItem
from .base import UEBase
from .properties import ObjectProperty, ObjectIndex, Property

from ark.asset import findComponentExports

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__all__ = (
    'AssetLoader',
    'load_file_into_memory',
    'ModResolver',
    'IniModResolver',
)


class ModResolver(ABC):
    '''Abstract class a mod resolver must implement.'''

    def initialise(self):
        pass

    @abstractmethod
    def get_name_from_id(self, modid: int) -> str:
        pass

    @abstractmethod
    def get_id_from_name(self, name: str) -> int:
        pass


class IniModResolver(ModResolver):
    '''Old-style mod resolution by hand-crafted mods.ini.'''

    def __init__(self, filename='mods.ini'):
        self.filename = filename

    def initialise(self):
        config = ConfigParser(inline_comment_prefixes='#;')
        config.optionxform = lambda v: v  # keep exact case of mod names, please
        config.read(self.filename)
        self.mods_id_to_names = dict(config['ids'])
        self.mods_names_to_ids = dict((name.lower(), id) for id, name in config['ids'].items())
        # self.mods_id_to_longnames = dict(config['names'])
        return self

    def get_name_from_id(self, modid: int) -> str:
        name = self.mods_id_to_names.get(modid, None)
        return name

    # def get_longname_from_id(self, modid: int) -> str:
    #     name = self.mods_id_to_longnames.get(modid, None)
    #     return name

    def get_id_from_name(self, name: str) -> int:
        id = self.mods_names_to_ids.get(name.lower(), None)
        return id


class AssetLoader:
    def __init__(self, modresolver: ModResolver, assetpath='.'):
        self.cache = dict()
        self.asset_path = Path(assetpath)
        self.absolute_asset_path = self.asset_path.absolute()
        self.modresolver = modresolver
        self.modresolver.initialise()

    def clean_asset_name(self, name: str):
        path = Path(name.strip().strip('/'))

        # Remove .uasset, if present
        if path.suffix == '.uasset':
            path = path.with_suffix('')

        # Remove asset_path, if present
        try:
            path = path.relative_to(self.absolute_asset_path)
        except ValueError:
            # path is not under the absolute path
            pass

        # Convert mod names to numbers
        if len(path.parts) > 2 and path.parts[1].lower() == 'mods' and path.parts[2].isnumeric():
            mod_name = self.modresolver.get_name_from_id(path.parts[2])
            parts = list(path.parts)
            parts[2] = mod_name
            path = Path(*parts)

        # Change Content back to name, for cache consistency
        if len(path.parts) and path.parts[0].lower() == 'content':
            parts = list(path.parts)
            parts[0] = 'Game'
            path = Path(*parts)

        result = PurePosixPath(path)
        result = '/' + str(result)

        return result

    def wipe_cache(self):
        self.cache = dict()

    def convert_asset_name_to_path(self, name: str, partial=False):
        '''Get the filename from which an asset can be loaded.'''
        name = self.clean_asset_name(name)
        parts = name.strip('/').split('/')

        # Convert mod names to numbers
        if len(parts) > 2 and parts[1].lower() == 'mods' and not parts[2].isnumeric():
            parts[2] = self.modresolver.get_id_from_name(parts[2])

        # Game is replaced with Content
        if len(parts) and parts[0].lower() == 'game':
            parts[0] = 'Content'

        fullname = os.path.join(self.asset_path, *parts)
        if not partial:
            fullname += '.uasset'

        return fullname

    def get_mod_name(self, assetname: str):
        assert assetname is not None
        assetname = self.clean_asset_name(assetname)
        parts = assetname.strip('/').split('/')
        if len(parts) < 3:
            return None
        if parts[0].lower() != 'game' or parts[1].lower() != 'mods':
            return None
        mod = parts[2]
        if mod.isnumeric():
            mod = self.modresolver.get_name_from_id(mod)
        return mod

    def get_mod_descriptive_name(self, assetname: str):
        assert assetname is not None
        assetname = self.clean_asset_name(assetname)
        parts = assetname.strip('/').split('/')
        if len(parts) < 3:
            return None
        if parts[0].lower() != 'game' or parts[1].lower() != 'mods':
            return None
        mod = parts[2]
        id = mod
        if not mod.isnumeric():
            id = self.modresolver.get_id_from_name(id)
        longname = self.modresolver.get_longname_from_id(id)
        return longname

    def find_assetnames(self, regex, toppath='/', exclude: Union[str, Tuple[str]] = None):
        if exclude is None:
            excludes = ()
        elif isinstance(exclude, str):
            excludes = (exclude, )
        else:
            excludes = exclude

        toppath = self.convert_asset_name_to_path(toppath, partial=True)
        for path, dirs, files in os.walk(toppath):
            for filename in files:
                fullpath = os.path.join(path, filename)
                name, ext = os.path.splitext(fullpath)

                if not ext.lower() == '.uasset':
                    continue

                match = re.match(regex, name)
                if not match:
                    continue

                if any(re.match(exclude, name) for exclude in excludes):
                    continue

                assetname = self.clean_asset_name(fullpath)
                yield assetname

    def load_related(self, obj: UEBase):
        if isinstance(obj, Property):
            return self.load_related(obj.value)
        if isinstance(obj, ObjectProperty):
            return self.load_related(obj.value.value)
        if isinstance(obj, ImportTableItem):
            assetname = str(obj.namespace.value.name.value)
            loader = obj.asset.loader
            asset = loader[assetname]
            return asset

        raise ValueError(f"Unsupported type for load_releated '{type(obj)}'")

    def _load_raw_asset_from_file(self, filename: str):
        '''Load an asset given its filename into memory without parsing it.'''
        logger.info("Loading file:", filename)
        if not os.path.isabs(filename):
            filename = os.path.join(self.asset_path, filename)
        mem = load_file_into_memory(filename)
        return mem

    def _load_raw_asset(self, name: str):
        '''Load an asset given its asset name into memory without parsing it.'''
        name = self.clean_asset_name(name)
        logger.info(f"Loading asset: {name}")
        filename = self.convert_asset_name_to_path(name)
        mem = load_file_into_memory(filename)
        return mem

    def __getitem__(self, assetname: str):
        '''Load and parse the given asset, or fetch it from the cache if already loaded.'''
        assetname = self.clean_asset_name(assetname)
        asset = self.cache.get(assetname, None) or self._load_asset(assetname)
        return asset

    def __delitem__(self, assetname: str):
        '''Remove the specified assetname from the cache.'''
        assetname = self.clean_asset_name(assetname)
        del self.cache[assetname]

    def partially_load_asset(self, assetname: str):
        asset = self._load_asset(assetname, doNotLink=True)
        return asset

    def _load_asset(self, assetname: str, doNotLink=False):
        mem = self._load_raw_asset(assetname)
        stream = MemoryStream(mem, 0, len(mem))
        asset = UAsset(stream)
        asset.loader = self
        asset.assetname = assetname
        asset.name = assetname.split('/')[-1]
        asset.deserialise()
        if doNotLink:
            return asset
        asset.link()
        exports = list(findComponentExports(asset))
        if len(exports) > 1:
            import warnings
            warnings.warn(f'Found more than one component in {assetname}!')
        asset.default_export = exports[0] if len(exports) else None
        self.cache[assetname] = asset
        return asset

    # def _load_user_config(self):
    #     config = ConfigParser()
    #     config.read(os.path.join(self.configpath, 'user.ini'))
    #     asset_path = config.get('parser', 'assetpath', fallback='.')
    #     logger.info("Using asset path: " + asset_path)
    #     self.asset_path = asset_path
    #     self.normalised_asset_path = asset_path.lower().replace('\\', '/').lstrip('/')

    # def _load_mods_config(self):
    #     config = ConfigParser(inline_comment_prefixes='#;')
    #     config.optionxform = lambda v: v  # keep exact base of mod names, please
    #     config.read(os.path.join(self.configpath, 'mods.ini'))
    #     self.mods_numbers_to_names = dict(config['ids'])
    #     self.mods_names_to_numbers = dict(reversed(kvp) for kvp in config['ids'].items())
    #     self.mods_numbers_to_descriptions = dict(config['names'])


def load_file_into_memory(filename):
    with open(filename, 'rb') as f:
        data = f.read()
        mem = memoryview(data)
        return mem
