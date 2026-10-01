# -*- coding: utf-8 -*-
"""Unit tests for RemoteAdapterTool."""

import os
import json
from unittest.mock import MagicMock, patch

from resources.lib.common.os_detect import OSType


def test_remote_adapter_non_coreelec_guard(tmp_path):
    from resources.lib.tools.remote_adapter import RemoteAdapterTool

    tool = RemoteAdapterTool(
        keymaps_dir=str(tmp_path / "keymaps"),
        hwdb_dir=str(tmp_path / "hwdb.d"),
        flash_dir=str(tmp_path / "flash"),
        config_dir=str(tmp_path / "config"),
    )

    mock_sys = MagicMock()
    mock_sys.os_type = OSType.WINDOWS

    with patch("resources.lib.tools.remote_adapter.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.remote_adapter.dialog_ok") as mock_ok:
        tool.run({})
        mock_ok.assert_called_once()
        assert "CoreELEC" in mock_ok.call_args[0][1]


def test_remote_adapter_safe_xml_copy_does_not_delete_user_keymaps(tmp_path):
    from resources.lib.tools.remote_adapter import RemoteAdapterTool

    keymaps_dir = str(tmp_path / "keymaps")
    hwdb_dir = str(tmp_path / "hwdb.d")
    flash_dir = str(tmp_path / "flash")
    data_dir = str(tmp_path / "data" / "remotes")

    os.makedirs(keymaps_dir, exist_ok=True)
    os.makedirs(hwdb_dir, exist_ok=True)
    os.makedirs(flash_dir, exist_ok=True)

    # User's existing keymaps
    user_gen_xml = os.path.join(keymaps_dir, "gen.xml")
    user_kbd_xml = os.path.join(keymaps_dir, "keyboard.xml")
    with open(user_gen_xml, "w") as f:
        f.write("<keymap>user custom gen</keymap>")
    with open(user_kbd_xml, "w") as f:
        f.write("<keymap>user custom kbd</keymap>")

    # Mock remote source data with gen.xml
    remote_src = os.path.join(data_dir, "test_remote")
    os.makedirs(remote_src, exist_ok=True)
    with open(os.path.join(remote_src, "gen.xml"), "w") as f:
        f.write("<keymap>remote new gen</keymap>")

    tool = RemoteAdapterTool(
        keymaps_dir=keymaps_dir,
        hwdb_dir=hwdb_dir,
        flash_dir=flash_dir,
        backup_dir=str(tmp_path / "backup"),
        remotes_data_dir=data_dir,
    )

    remote_info = {"id": "test_remote", "name": "Test Remote"}
    with patch("resources.lib.tools.remote_adapter.xbmc.executebuiltin"), \
         patch("resources.lib.tools.remote_adapter.dialog_ok"):
        tool._apply_config("Title", remote_info)

    # CRITICAL: User's original files MUST NOT be deleted or overwritten
    assert os.path.exists(user_gen_xml)
    with open(user_gen_xml, "r") as f:
        assert f.read() == "<keymap>user custom gen</keymap>"

    assert os.path.exists(user_kbd_xml)
    with open(user_kbd_xml, "r") as f:
        assert f.read() == "<keymap>user custom kbd</keymap>"

    # Remote config was copied with safe prefix
    new_xml = os.path.join(keymaps_dir, "remote_adapter_gen.xml")
    assert os.path.exists(new_xml)
    with open(new_xml, "r") as f:
        assert f.read() == "<keymap>remote new gen</keymap>"


def test_remote_adapter_snapshot_backup_and_restore(tmp_path):
    from resources.lib.tools.remote_adapter import RemoteAdapterTool

    keymaps_dir = str(tmp_path / "keymaps")
    hwdb_dir = str(tmp_path / "hwdb.d")
    flash_dir = str(tmp_path / "flash")
    backup_dir = str(tmp_path / "backup")
    data_dir = str(tmp_path / "data" / "remotes")

    os.makedirs(keymaps_dir, exist_ok=True)
    os.makedirs(hwdb_dir, exist_ok=True)
    os.makedirs(flash_dir, exist_ok=True)

    # Initial state before adaptation:
    # 1. Existing remote.conf in /flash
    orig_conf = os.path.join(flash_dir, "remote.conf")
    with open(orig_conf, "w") as f:
        f.write("factory_remote_code=0x1234")

    # 2. Existing hwdb
    orig_hwdb = os.path.join(hwdb_dir, "custom.hwdb")
    with open(orig_hwdb, "w") as f:
        f.write("KEYBOARD_KEY_123=play")

    # Mock new remote with different hwdb and xml
    remote_src = os.path.join(data_dir, "remote_b")
    os.makedirs(remote_src, exist_ok=True)
    with open(os.path.join(remote_src, "remote_b.hwdb"), "w") as f:
        f.write("KEYBOARD_KEY_456=stop")
    with open(os.path.join(remote_src, "remote_b.xml"), "w") as f:
        f.write("<keymap>b</keymap>")

    tool = RemoteAdapterTool(
        keymaps_dir=keymaps_dir,
        hwdb_dir=hwdb_dir,
        flash_dir=flash_dir,
        backup_dir=backup_dir,
        remotes_data_dir=data_dir,
    )

    # Step 1: Apply remote_b (auto creates snapshot backup)
    with patch("resources.lib.tools.remote_adapter.dialog_yesno", return_value=False), \
         patch("resources.lib.tools.remote_adapter.run_command", return_value=(0, "", "")):
        tool._apply_config("Title", {"id": "remote_b", "name": "Remote B"})

    # Verify backup exists
    assert os.path.exists(os.path.join(backup_dir, "remote.conf"))
    assert os.path.exists(os.path.join(backup_dir, "hwdb.d", "custom.hwdb"))

    # Verify new remote files are active
    assert os.path.exists(os.path.join(hwdb_dir, "remote_b.hwdb"))
    assert os.path.exists(os.path.join(keymaps_dir, "remote_adapter_remote_b.xml"))

    # Step 2: Restore backup
    with patch("resources.lib.tools.remote_adapter.dialog_yesno", return_value=False), \
         patch("resources.lib.tools.remote_adapter.run_command", return_value=(0, "", "")):
        tool._restore_backup("Title")

    # Verify restored state:
    # 1. remote_b files removed
    assert not os.path.exists(os.path.join(hwdb_dir, "remote_b.hwdb"))
    assert not os.path.exists(os.path.join(keymaps_dir, "remote_adapter_remote_b.xml"))
    # 2. original files restored
    assert os.path.exists(os.path.join(hwdb_dir, "custom.hwdb"))
    assert os.path.exists(orig_conf)
    with open(orig_conf, "r") as f:
        assert f.read() == "factory_remote_code=0x1234"


def test_remote_adapter_factory_conf_protection(tmp_path):
    from resources.lib.tools.remote_adapter import RemoteAdapterTool

    keymaps_dir = str(tmp_path / "keymaps")
    hwdb_dir = str(tmp_path / "hwdb.d")
    flash_dir = str(tmp_path / "flash")
    data_dir = str(tmp_path / "data" / "remotes")

    os.makedirs(keymaps_dir, exist_ok=True)
    os.makedirs(hwdb_dir, exist_ok=True)
    os.makedirs(flash_dir, exist_ok=True)

    # Initial factory remote.conf
    factory_conf = os.path.join(flash_dir, "remote.conf")
    with open(factory_conf, "w") as f:
        f.write("original factory remote config")

    # New bluetooth remote without .conf
    bt_remote_dir = os.path.join(data_dir, "bt_remote")
    os.makedirs(bt_remote_dir, exist_ok=True)
    with open(os.path.join(bt_remote_dir, "bt.hwdb"), "w") as f:
        f.write("BT=1")

    tool = RemoteAdapterTool(
        keymaps_dir=keymaps_dir,
        hwdb_dir=hwdb_dir,
        flash_dir=flash_dir,
        backup_dir=str(tmp_path / "backup"),
        remotes_data_dir=data_dir,
    )

    with patch("resources.lib.tools.remote_adapter.dialog_yesno", return_value=False), \
         patch("resources.lib.tools.remote_adapter.run_command", return_value=(0, "", "")):
        tool._apply_config("Title", {"id": "bt_remote", "name": "BT Remote"})

    # Original remote.conf should NOT be deleted, but preserved as .factory
    protected_conf = os.path.join(flash_dir, "remote.conf.factory")
    assert os.path.exists(protected_conf)
    with open(protected_conf, "r") as f:
        assert f.read() == "original factory remote config"


def test_remote_adapter_menu_dispatch(tmp_path):
    from resources.lib.tools.remote_adapter import RemoteAdapterTool

    tool = RemoteAdapterTool(
        keymaps_dir=str(tmp_path / "keymaps"),
        hwdb_dir=str(tmp_path / "hwdb.d"),
        flash_dir=str(tmp_path / "flash"),
        config_dir=str(tmp_path / "config"),
    )
    os.makedirs(str(tmp_path / "config"), exist_ok=True)

    mock_sys = MagicMock()
    mock_sys.os_type = OSType.COREELEC

    # Test cancel (-1)
    with patch("resources.lib.tools.remote_adapter.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.remote_adapter.dialog_select", return_value=-1), \
         patch.object(tool, "_apply_config") as mock_apply, \
         patch.object(tool, "_restore_backup") as mock_restore:
        tool.run({})
        mock_apply.assert_not_called()
        mock_restore.assert_not_called()

    # Test select remote (e.g. index 0)
    with patch("resources.lib.tools.remote_adapter.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.remote_adapter.dialog_select", return_value=0), \
         patch("resources.lib.tools.remote_adapter.dialog_yesno", return_value=True), \
         patch.object(tool, "_apply_config") as mock_apply:
        tool.run({})
        mock_apply.assert_called_once()
        assert mock_apply.call_args[0][1]["id"] == "6bur02remote"

    # Test select restore (index 11)
    with patch("resources.lib.tools.remote_adapter.get_system_info", return_value=mock_sys), \
         patch("resources.lib.tools.remote_adapter.dialog_select", return_value=len(tool.REMOTES)), \
         patch.object(tool, "_restore_backup") as mock_restore:
        tool.run({})
        mock_restore.assert_called_once()


def test_remote_adapter_reboot_dispatch(tmp_path):
    from resources.lib.tools.remote_adapter import RemoteAdapterTool

    data_dir = str(tmp_path / "data" / "remotes")
    os.makedirs(os.path.join(data_dir, "hwdb_remote"), exist_ok=True)
    with open(os.path.join(data_dir, "hwdb_remote", "test.hwdb"), "w") as f:
        f.write("TEST=1")

    tool = RemoteAdapterTool(
        keymaps_dir=str(tmp_path / "keymaps"),
        hwdb_dir=str(tmp_path / "hwdb.d"),
        flash_dir=str(tmp_path / "flash"),
        remotes_data_dir=data_dir,
    )

    with patch("resources.lib.tools.remote_adapter.dialog_yesno", return_value=True), \
         patch.object(tool, "_do_reboot") as mock_reboot:
        tool._apply_config("Title", {"id": "hwdb_remote", "name": "HWDB Remote"})
        mock_reboot.assert_called_once()

