# -*- coding: utf-8 -*-
"""Unit tests for AutoRebootTool."""

import os
from unittest.mock import MagicMock, patch

from resources.lib.common.os_detect import OSType, SystemInfo


def test_auto_reboot_non_coreelec_guard(tmp_path):
    from resources.lib.tools.auto_reboot import AutoRebootTool

    tool = AutoRebootTool(systemd_dir=str(tmp_path / "system.d"), config_dir=str(tmp_path / "config"))
    mock_sys = MagicMock()
    mock_sys.os_type = OSType.WINDOWS

    with patch("resources.lib.tools.auto_reboot.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.auto_reboot.dialog_ok") as mock_ok:
        tool.run({})
        mock_ok.assert_called_once()
        assert "CoreELEC" in mock_ok.call_args[0][1]


def test_auto_reboot_get_current_time(tmp_path):
    from resources.lib.tools.auto_reboot import AutoRebootTool

    systemd_dir = str(tmp_path / "system.d")
    tool = AutoRebootTool(systemd_dir=systemd_dir, config_dir=str(tmp_path / "config"))

    # Missing file returns None
    assert tool._get_current_time() is None

    # Normal format 04:30
    os.makedirs(systemd_dir, exist_ok=True)
    timer_path = os.path.join(systemd_dir, "daily-reboot.timer")
    with open(timer_path, "w", encoding="utf-8") as f:
        f.write("[Timer]\nOnCalendar=*-*-* 04:30:00\n")
    assert tool._get_current_time() == "04:30"

    # Single digit hour 4:15 -> padded to 04:15
    with open(timer_path, "w", encoding="utf-8") as f:
        f.write("[Timer]\nOnCalendar=*-*-* 4:15:00\n")
    assert tool._get_current_time() == "04:15"


def test_auto_reboot_set_timer_success(tmp_path):
    from resources.lib.tools.auto_reboot import AutoRebootTool

    systemd_dir = str(tmp_path / "system.d")
    tool = AutoRebootTool(systemd_dir=systemd_dir, config_dir=str(tmp_path / "config"))

    with patch("resources.lib.tools.auto_reboot.dialog_numeric", return_value="05:00"), \
         patch("resources.lib.tools.auto_reboot.run_command", return_value=(0, "", "")) as mock_cmd, \
         patch("resources.lib.tools.auto_reboot.dialog_ok") as mock_ok:
        tool._set_timer("Title", "04:00")

    service_file = os.path.join(systemd_dir, "daily-reboot.service")
    timer_file = os.path.join(systemd_dir, "daily-reboot.timer")

    assert os.path.exists(service_file)
    assert os.path.exists(timer_file)

    with open(service_file, "r", encoding="utf-8") as f:
        svc_content = f.read()
        assert "UPTIME" in svc_content
        assert "-gt 600" in svc_content
        assert "/usr/sbin/reboot" in svc_content

    with open(timer_file, "r", encoding="utf-8") as f:
        tmr_content = f.read()
        assert "OnCalendar=*-*-* 05:00:00" in tmr_content

    commands = [c[0][0] for c in mock_cmd.call_args_list]
    assert "systemctl daemon-reload" in commands
    assert "systemctl enable daily-reboot.timer" in commands
    assert "systemctl restart daily-reboot.timer" in commands
    mock_ok.assert_called_once()


def test_auto_reboot_disable_timer(tmp_path):
    from resources.lib.tools.auto_reboot import AutoRebootTool

    systemd_dir = str(tmp_path / "system.d")
    os.makedirs(systemd_dir, exist_ok=True)
    service_file = os.path.join(systemd_dir, "daily-reboot.service")
    timer_file = os.path.join(systemd_dir, "daily-reboot.timer")

    with open(service_file, "w") as f:
        f.write("test service")
    with open(timer_file, "w") as f:
        f.write("test timer")

    tool = AutoRebootTool(systemd_dir=systemd_dir, config_dir=str(tmp_path / "config"))

    with patch("resources.lib.tools.auto_reboot.run_command", return_value=(0, "", "")) as mock_cmd, \
         patch("resources.lib.tools.auto_reboot.dialog_ok") as mock_ok:
        tool._disable_timer("Title")

    assert not os.path.exists(service_file)
    assert not os.path.exists(timer_file)

    commands = [c[0][0] for c in mock_cmd.call_args_list]
    assert "systemctl stop daily-reboot.timer" in commands
    assert "systemctl disable daily-reboot.timer" in commands
    assert "systemctl daemon-reload" in commands
    mock_ok.assert_called_once()


def test_auto_reboot_menu_dispatch(tmp_path):
    from resources.lib.tools.auto_reboot import AutoRebootTool

    systemd_dir = str(tmp_path / "system.d")
    config_dir = str(tmp_path / "config")
    os.makedirs(config_dir, exist_ok=True)
    tool = AutoRebootTool(systemd_dir=systemd_dir, config_dir=config_dir)

    mock_sys = MagicMock()
    mock_sys.os_type = OSType.COREELEC

    # Test cancel (-1)
    with patch("resources.lib.tools.auto_reboot.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.auto_reboot.dialog_select", return_value=-1), \
         patch.object(tool, "_set_timer") as mock_set, \
         patch.object(tool, "_disable_timer") as mock_disable:
        tool.run({})
        mock_set.assert_not_called()
        mock_disable.assert_not_called()

    # Test select 0 (set timer)
    with patch("resources.lib.tools.auto_reboot.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.auto_reboot.dialog_select", return_value=0), \
         patch.object(tool, "_set_timer") as mock_set:
        tool.run({})
        mock_set.assert_called_once()

    # Test select 1 (disable timer)
    with patch("resources.lib.tools.auto_reboot.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.auto_reboot.dialog_select", return_value=1), \
         patch.object(tool, "_disable_timer") as mock_disable:
        tool.run({})
        mock_disable.assert_called_once()

