from logging import NullHandler, getLogger
from pathlib import PurePosixPath
from typing import *

from automate.hierarchy_exporter import JsonHierarchyExportStage
from export.wiki.types import MissionType
from ue.asset import UAsset
from ue.proxy import UEProxyStructure

__all__ = [
    'MissionsStage',
]

logger = getLogger(__name__)
logger.addHandler(NullHandler())


class MissionsStage(JsonHierarchyExportStage):
    def get_skip(self):
        return not self.manager.config.export_wiki.ExportMissions

    def get_format_version(self) -> str:
        return "1"

    def get_field(self) -> str:
        return "missions"

    def get_use_pretty(self) -> bool:
        return bool(self.manager.config.export_wiki.PrettyJson)

    def get_ue_type(self) -> str:
        return MissionType.get_ue_type()

    def extract(self, proxy: UEProxyStructure) -> Any:
        mission: MissionType = cast(MissionType, proxy)

        v: Dict[str, Any] = dict()
        v['bp'] = proxy.get_source().fullname
        v['name'] = mission.MissionDisplayName[0]
        v['description'] = mission.MissionDescription[0]
        v['rewards'] = dict(hexagons=convert_hexagon_values(mission), )

        return v


def convert_hexagon_values(mission: MissionType) -> Dict[str, Any]:
    v: Dict[str, Any] = dict()

    v['totalQty'] = mission.HexagonsOnCompletion[0]
    if mission.bDivideHexogonsOnCompletion[0]:
        v['divideByPlayers'] = True

    return v
