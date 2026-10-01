# -*- coding: utf-8 -*-
"""Unit tests for URL routing and parameter parsing."""

from unittest.mock import MagicMock, patch
from resources.lib.router import (
    close_container,
    menu_entries,
    parse_params,
    route,
    run_tool,
    show_dialog_menu,
    show_main_menu,
)


def test_parse_params():
    assert parse_params("") == {}
    assert parse_params("?") == {}
    assert parse_params("?action=speedtest") == {"action": "speedtest"}
    assert parse_params("action=speedtest&sub=start") == {"action": "speedtest", "sub": "start"}
    assert parse_params("?action=disk_bench&size=128") == {"action": "disk_bench", "size": "128"}


def test_close_container_with_valid_handle():
    with patch("xbmcplugin.endOfDirectory") as mock_end:
        close_container(10)
        mock_end.assert_called_once_with(10, succeeded=False, updateListing=False, cacheToDisc=False)


def test_close_container_with_negative_handle():
    with patch("xbmcplugin.endOfDirectory") as mock_end:
        close_container(-1)
        mock_end.assert_not_called()


def test_menu_entries_completeness():
    entries = menu_entries()
    assert len(entries) >= 7  # All registered tools + system info
    actions = [e[0] for e in entries]
    assert "speedtest" in actions
    assert "kodi_optimizer" in actions
    assert "firmware_settings" in actions
    assert "remote_adapter" in actions
    assert "auto_reboot" in actions
    assert "about" in actions


def test_new_tools_registered():
    from resources.lib.tools import RemoteAdapterTool, AutoRebootTool
    from resources.lib.tools.base_tool import ToolRegistry

    tool_ra = ToolRegistry.get("remote_adapter")
    assert tool_ra is not None
    assert isinstance(tool_ra, RemoteAdapterTool)
    assert tool_ra.order == 25

    tool_ar = ToolRegistry.get("auto_reboot")
    assert tool_ar is not None
    assert isinstance(tool_ar, AutoRebootTool)
    assert tool_ar.order == 35


def test_show_about_info():
    from resources.lib.router import show_about_info
    with patch("resources.lib.router.dialog_textviewer") as mock_tv:
        show_about_info()
        mock_tv.assert_called_once()
        text = mock_tv.call_args[0][1]
        assert "Remote Control Auto-Adapter" in text
        assert "Daily Auto Reboot" in text



def test_firmware_settings_registered():
    from resources.lib.tools import FirmwareSettingsTool
    from resources.lib.tools.base_tool import ToolRegistry
    tool = ToolRegistry.get("firmware_settings")
    assert tool is not None
    assert isinstance(tool, FirmwareSettingsTool)
    assert tool.id == "firmware_settings"
    assert tool.order == 17




def test_run_tool_error_handling():
    with patch("resources.lib.tools.ToolRegistry.dispatch", side_effect=RuntimeError("Simulated error")), \
         patch("resources.lib.router.show_notification") as mock_notify:
        run_tool("speedtest")
        mock_notify.assert_called_once()
        assert "speedtest" in mock_notify.call_args[0][1]


def test_route_dispatches_main_menu_and_closes_container():
    with patch("resources.lib.router.close_container") as mock_close, \
         patch("resources.lib.router.show_dialog_menu") as mock_menu:
        route(["plugin://plugin.program.systemtools/", "5", ""])
        mock_close.assert_called_once_with(5)
        mock_menu.assert_called_once()


def test_route_direct_action():
    with patch("resources.lib.router.run_tool") as mock_run:
        route(["plugin://plugin.program.systemtools/", "-1", "?action=speedtest"])
        mock_run.assert_called_once_with("speedtest")


def test_show_dialog_menu_loop_and_exit():
    with patch("resources.lib.router.dialog_select_details", side_effect=[0, -1]) as mock_dialog, \
         patch("resources.lib.router.run_entry") as mock_run:
        show_dialog_menu("test")
        assert mock_dialog.call_count == 2
        mock_run.assert_called_once()
