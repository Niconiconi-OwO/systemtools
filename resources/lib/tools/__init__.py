# -*- coding: utf-8 -*-
"""Toolbox tools registry and exports."""

from .base_tool import BaseTool, ToolRegistry
from .disk_benchmark import DiskBenchmarkTool
from .dtb_tool import DtbTool, is_dtb_protected, set_dtb_protection
from .firmware_settings import FirmwareSettingsTool
from .kodi_optimizer import KodiOptimizerTool
from .log_cleaner import LogCleanerTool
from .net_config import NetConfigTool
from .net_speedtest import NetSpeedtestTool
from .os_switcher import OsSwitcherTool
from .ram_cleaner import RamCleanerTool
from .remote_adapter import RemoteAdapterTool
from .auto_reboot import AutoRebootTool

__all__ = [
    "BaseTool",
    "ToolRegistry",
    "OsSwitcherTool",
    "DtbTool",
    "RamCleanerTool",
    "KodiOptimizerTool",
    "FirmwareSettingsTool",
    "NetSpeedtestTool",
    "DiskBenchmarkTool",
    "NetConfigTool",
    "LogCleanerTool",
    "is_dtb_protected",
    "set_dtb_protection",
    "RemoteAdapterTool",
    "AutoRebootTool"
]

