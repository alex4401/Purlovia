from logging import NullHandler, getLogger
from pathlib import PurePosixPath
from typing import *

from automate.hierarchy_exporter import JsonHierarchyExportStage
from export.wiki.types import HexagonTradableOption
from ue.asset import UAsset
from ue.proxy import UEProxyStructure

__all__ = [
    'TradesStage',
]

logger = getLogger(__name__)
logger.addHandler(NullHandler())


class TradesStage(JsonHierarchyExportStage):
    def get_skip(self):
        return not self.manager.config.export_wiki.ExportTrades

    def get_format_version(self) -> str:
        return "1"

    def get_field(self) -> str:
        return "trades"

    def get_use_pretty(self) -> bool:
        return bool(self.manager.config.export_wiki.PrettyJson)

    def get_ue_type(self) -> str:
        return HexagonTradableOption.get_ue_type()

    def extract(self, proxy: UEProxyStructure) -> Any:
        trade: HexagonTradableOption = cast(HexagonTradableOption, proxy)

        item = trade.get('ItemClass', fallback=None)
        if not item:
            return None

        v: Dict[str, Any] = dict()
        v['bp'] = proxy.get_source().fullname
        v['itemBP'] = trade.ItemClass[0]
        v['qty'] = trade.Quantity[0]
        v['cost'] = trade.ItemCost[0]

        return v
