import argparse
import logging
import logging.config
import os
import sys
from pathlib import Path
from typing import *

import yaml

import ark.discovery
from config import ConfigFile, get_global_config
from export.asb.root import ASBRoot
from export.example.root import ExampleRoot
from export.wiki.root import WikiRoot

from .ark import ArkSteamManager
from .exporter import ExportManager
from .git import GitManager
from .notification import handle_exception

# pylint: enable=invalid-name

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
logger.addHandler(logging.NullHandler())


def setup_logging(path='config/logging.yaml', level=logging.INFO):
    '''Setup logging configuration.'''
    if os.path.exists(path):
        with open(path, 'rt') as log_config_file:
            config = yaml.safe_load(log_config_file)
        Path('logs').mkdir(parents=True, exist_ok=True)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=level)

    logging.captureWarnings(True)

    root_logger = logging.getLogger()
    logging.addLevelName(100, 'STARTUP')
    root_logger.log(100, '')
    root_logger.log(100, '-' * 100)
    root_logger.log(100, '')


EPILOG = '''example: python -m automate --skip-install'''

DESCRIPTION = '''Perform an automated run of Purlovia, optionally overriding config or individual parts of the process.'''


def modlist(value: str) -> Tuple[str, ...]:
    value = value.strip()
    inputs = [v.strip() for v in value.split(',')]
    mods = tuple(v for v in inputs if v)
    for modid in mods:
        as_int = int(modid)  # pylint: disable=unused-variable  # For type-checking only
    return mods


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("automate", description=DESCRIPTION, epilog=EPILOG)

    exclusive = parser.add_mutually_exclusive_group()
    exclusive.add_argument('--live', action='store_true', help='enable live mode [requires git identity]')

    parser.add_argument('--remove-cache', action='store_true', help='remove the (dev only) asset tree cache')

    parser.add_argument('--skip-install', action='store_true', help='skip install/update of game and mods')
    parser.add_argument('--skip-extract', action='store_true', help='skip extracting all data completely')

    parser.add_argument('--skip-extract-asb', action='store_true', help='skip extracting all ASB data completely')
    parser.add_argument('--skip-asb-species', action='store_true', help='skip extracting species for ASB')

    parser.add_argument('--skip-extract-wiki', action='store_true', help='skip extracting all wiki data completely')
    parser.add_argument('--skip-wiki-maps', action='store_true', help='skip extracting map data for the wiki')
    parser.add_argument('--skip-wiki-vanilla-maps', action='store_true', help='skip extracting vanilla map data for the wiki')
    parser.add_argument('--skip-wiki-spawn-groups', action='store_true', help='skip extracting spawning groups for the wiki')
    parser.add_argument('--skip-wiki-engrams', action='store_true', help='skip extracting engrams for the wiki')
    parser.add_argument('--skip-wiki-items', action='store_true', help='skip extracting items for the wiki')
    parser.add_argument('--skip-wiki-drops', action='store_true', help='skip extracting drops for the wiki')
    parser.add_argument('--skip-wiki-loot-crates', action='store_true', help='skip extracting loot crates for the wiki')
    parser.add_argument('--skip-wiki-species', action='store_true', help='skip extracting species for the wiki')
    parser.add_argument('--skip-wiki-trades', action='store_true', help='skip extracting HLN-A trades for the wiki')
    parser.add_argument('--skip-wiki-missions', action='store_true', help='skip extracting missions for the wiki')

    parser.add_argument('--skip-process-spawns', action='store_true', help='skip processing spawning data for the wiki')
    parser.add_argument('--skip-process-biomes', action='store_true', help='skip processing biomes for the wiki')

    parser.add_argument('--skip-commit', action='store_true', help='skip git commit of the output repo (use dry-run mode)')
    parser.add_argument('--skip-pull', action='store_true', help='skip git pull or reset of the output repo')
    parser.add_argument('--skip-push', action='store_true', help='skip git push of the output repo')

    parser.add_argument('--notify', action='store_true', help='enable sending error notifications')

    parser.add_argument('--mods', action='store', type=modlist, help='override which mods to export (comma-separated)')

    return parser


def handle_args(args: Any) -> ConfigFile:
    setup_logging(path='config/logging.yaml')

    config = get_global_config()

    if args.live:
        logger.info('LIVE mode enabled')
        config.settings.SkipGit = False
        config.git.UseReset = True
        config.git.UseIdentity = True
        config.errors.SendNotifications = True
    else:
        logger.info('DEV mode enabled')
        config.git.UseIdentity = False
        config.git.SkipCommit = True
        config.git.SkipPush = True
        config.errors.SendNotifications = False

    config.dev.DevMode = not args.live

    if args.notify:  # to enable notifications in dev mode
        config.errors.SendNotifications = True

    if args.remove_cache:
        config.dev.ClearHierarchyCache = True

    if args.skip_install:
        config.settings.SkipInstall = True
    if args.skip_extract:
        config.settings.SkipExtract = True

    # ASB extract stages
    if args.skip_extract_asb:
        config.export_asb.Skip = True
    if args.skip_asb_species:
        config.export_asb.ExportSpecies = False

    # Wiki extract stages
    if args.skip_extract_wiki:
        config.export_wiki.Skip = True
    if args.skip_wiki_maps:
        config.export_wiki.ExportMaps = False
    if args.skip_wiki_vanilla_maps:
        config.export_wiki.ExportVanillaMaps = False
    if args.skip_wiki_spawn_groups:
        config.export_wiki.ExportSpawningGroups = False
    if args.skip_wiki_engrams:
        config.export_wiki.ExportEngrams = False
    if args.skip_wiki_items:
        config.export_wiki.ExportItems = False
    if args.skip_wiki_drops:
        config.export_wiki.ExportDrops = False
    if args.skip_wiki_loot_crates:
        config.export_wiki.ExportLootCrates = False
    if args.skip_wiki_species:
        config.export_wiki.ExportSpecies = False
    if args.skip_wiki_trades:
        config.export_wiki.ExportTrades = False
    if args.skip_wiki_missions:
        config.export_wiki.ExportMissions = False

    # Processing stages
    #if args.skip_processing:
    #    config.processing.Skip = True
    if args.skip_process_spawns:
        config.processing.ProcessSpawns = False
    if args.skip_process_biomes:
        config.processing.ProcessBiomes = False

    # Git actions
    if args.skip_pull:
        config.git.SkipPull = True
    if args.skip_commit:
        config.git.SkipCommit = True
    if args.skip_push:
        config.git.SkipPush = True

    if args.mods is not None:
        config.extract_mods = args.mods

    return config


def run(config: ConfigFile):

    # Run update then export
    try:
        # Get mod list
        mods = config.mods

        # Update game ad mods
        arkman = ArkSteamManager(config=config)
        arkman.ensureSteamCmd()
        arkman.ensureGameUpdated()
        arkman.ensureModsUpdated(mods)

        # Ensure Git is setup and ready
        git = GitManager(config=config)
        git.before_exports()

        # Initialise the asset hierarchy, scanning everything
        ark.discovery.initialise_hierarchy(arkman, config)

        # Handle exporting
        exporter = ExportManager(arkman, git, config)
        # exporter.add_root(ExampleRoot())
        exporter.add_root(ASBRoot())
        exporter.add_root(WikiRoot())
        exporter.perform()

        # Push any changes
        git.finish()

        logger.info('Automation completed')

    except:  # pylint: disable=bare-except
        handle_exception(logfile='logs/errors.log', config=config)
        logger.exception('Caught exception during automation run. Aborting.')


def main():
    parser = create_parser()
    args = parser.parse_args()
    config = handle_args(args)
    run(config)
