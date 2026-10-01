# -*- coding: utf-8 -*-
"""Unit tests for CoreELEC multi-version switcher and tar unpacker."""

import io
import json
import os
import tarfile
from unittest.mock import MagicMock, patch

import xbmcvfs

from resources.lib.tools.os_switcher import OsSwitcherTool, parse_tar_version_info


def create_dummy_ce_tar(tar_path: str):
    """Helper to create a mock CoreELEC update .tar archive."""
    with tarfile.open(tar_path, "w") as tar:
        # target/KERNEL
        kernel_data = b"MOCK_KERNEL_BINARY_DATA"
        k_info = tarfile.TarInfo(name="target/KERNEL")
        k_info.size = len(kernel_data)
        tar.addfile(k_info, io.BytesIO(kernel_data))

        # target/SYSTEM
        system_data = b"MOCK_SYSTEM_SQUASHFS_DATA"
        s_info = tarfile.TarInfo(name="target/SYSTEM")
        s_info.size = len(system_data)
        tar.addfile(s_info, io.BytesIO(system_data))

        # target/SYSTEM.md5
        md5_data = b"d41d8cd98f00b204e9800998ecf8427e  SYSTEM\n"
        m_info = tarfile.TarInfo(name="target/SYSTEM.md5")
        m_info.size = len(md5_data)
        tar.addfile(m_info, io.BytesIO(md5_data))


def test_parse_tar_version_timestamps():
    """Test disambiguation between builds differing only by timestamps."""
    f1 = "CoreELEC-Amlogic-ng.arm-21.3-Omega_avdvplus_F10_20260922221205.tar"
    f2 = "CoreELEC-Amlogic-ng.arm-21.3-Omega_avdvplus_F10_20260921090828.tar"

    s1, d1, b1 = parse_tar_version_info(f1)
    s2, d2, b2 = parse_tar_version_info(f2)

    assert d1 == "21.3-Omega_avdvplus_F10 [09-22 22:12]"
    assert b1 == "2026-09-22 22:12:05"

    assert d2 == "21.3-Omega_avdvplus_F10 [09-21 09:08]"
    assert b2 == "2026-09-21 09:08:28"

    # Distinct display names so they never collide
    assert d1 != d2
    assert s1 != s2


def test_os_switcher_tar_unpack_and_version_pool(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    # 1. Create a mock update tar
    tar_file = str(tmp_path / "CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260922221205.tar")
    create_dummy_ce_tar(tar_file)

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    # Mock dialog inputs
    with patch("resources.lib.tools.os_switcher.dialog_browse", return_value=tar_file), \
         patch("resources.lib.tools.os_switcher.dialog_input", return_value="21.3-Omega_avdvplus_F10 [09-22 22:12]"), \
         patch("resources.lib.tools.os_switcher.dialog_yesno", return_value=False):
        tool._action_import_tar("CoreELEC Version Switcher")

    saved = tool._get_saved_versions()
    displays = [s["display_name"] for s in saved]
    assert "21.3-Omega_avdvplus_F10 [09-22 22:12]" in displays
    # The tar file should still exist since dialog_yesno returned False
    assert os.path.exists(tar_file)


def test_os_switcher_tar_import_with_delete_tar(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    tar_file = str(tmp_path / "CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260921090828.tar")
    create_dummy_ce_tar(tar_file)
    assert os.path.exists(tar_file)

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    # First dialog_yesno (delete tar): True; Second dialog_yesno (switch now): False
    with patch("resources.lib.tools.os_switcher.dialog_browse", return_value=tar_file), \
         patch("resources.lib.tools.os_switcher.dialog_input", return_value="21.3-Omega_avdvplus_F10 [09-21 09:08]"), \
         patch("resources.lib.tools.os_switcher.dialog_yesno", side_effect=[True, False]):
        tool._action_import_tar("CoreELEC Version Switcher")

    # Tar file should be deleted from disk
    assert not os.path.exists(tar_file)
    # But version should be extracted and saved
    saved = tool._get_saved_versions()
    displays = [s["display_name"] for s in saved]
    assert "21.3-Omega_avdvplus_F10 [09-21 09:08]" in displays


def test_os_switcher_switch_to_version(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)

    target_vdir = os.path.join(versions_dir, "CE-21.0-Official")
    os.makedirs(target_vdir, exist_ok=True)
    with open(os.path.join(target_vdir, "KERNEL.img"), "wb") as f:
        f.write(b"OFFICIAL_KERNEL")
    with open(os.path.join(target_vdir, "SYSTEM"), "wb") as f:
        f.write(b"OFFICIAL_SYSTEM")
    with open(os.path.join(target_vdir, "guisettings.xml"), "w") as f:
        f.write("<settings>official</settings>")

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    with patch.object(tool, "_do_reboot") as mock_reboot, \
         patch.object(tool, "_set_flash_writable", return_value=True), \
         patch.object(tool, "_set_flash_readonly"):
        tool._switch_to_version_direct("CE-21.0-Official", "Title")
        assert mock_reboot.called

    assert os.path.exists(os.path.join(flash_dir, "KERNEL.img"))
    assert os.path.exists(os.path.join(flash_dir, "SYSTEM"))
    with open(os.path.join(flash_dir, "SYSTEM"), "rb") as f:
        assert f.read() == b"OFFICIAL_SYSTEM"


def test_os_switcher_backup_current(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)

    with open(os.path.join(flash_dir, "KERNEL.img"), "wb") as f:
        f.write(b"LIVE_KERNEL")
    with open(os.path.join(flash_dir, "SYSTEM"), "wb") as f:
        f.write(b"LIVE_SYSTEM")

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    with patch("resources.lib.tools.os_switcher.dialog_input", return_value="LiveBackup"):
        tool._action_backup_current("Backup")

    saved = tool._get_saved_versions()
    displays = [s["display_name"] for s in saved]
    assert "LiveBackup" in displays


def test_os_switcher_delete_version(tmp_path):
    versions_dir = str(tmp_path / "versions")
    vdir = os.path.join(versions_dir, "OldVersion")
    os.makedirs(vdir, exist_ok=True)
    with open(os.path.join(vdir, "SYSTEM"), "w") as f:
        f.write("test")

    tool = OsSwitcherTool(versions_dir=versions_dir)
    assert any(s["name"] == "OldVersion" for s in tool._get_saved_versions())

    with patch("resources.lib.tools.os_switcher.dialog_select", return_value=0), \
         patch("resources.lib.tools.os_switcher.dialog_yesno", return_value=True):
        tool._action_delete_version("Delete")

    assert not any(s["name"] == "OldVersion" for s in tool._get_saved_versions())


def test_os_switcher_tar_import_from_smb(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    local_tar = str(tmp_path / "CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260922221205.tar")
    create_dummy_ce_tar(local_tar)

    smb_url = "smb://192.168.1.100/share/CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260922221205.tar"
    xbmcvfs.File.register_url(smb_url, local_tar)

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    try:
        with patch("resources.lib.tools.os_switcher.dialog_browse", return_value=smb_url), \
             patch("resources.lib.tools.os_switcher.dialog_input", return_value="21.3-Omega_avdvplus_F10 [09-22 22:12]"), \
             patch("resources.lib.tools.os_switcher.dialog_yesno", return_value=False):
            tool._action_import_tar("CoreELEC Version Switcher")

        saved = tool._get_saved_versions()
        displays = [s["display_name"] for s in saved]
        assert "21.3-Omega_avdvplus_F10 [09-22 22:12]" in displays

        # Check extracted files
        target_entry = [s for s in saved if s["display_name"] == "21.3-Omega_avdvplus_F10 [09-22 22:12]"][0]
        vdir = os.path.join(versions_dir, target_entry["name"])
        assert os.path.exists(os.path.join(vdir, "KERNEL.img"))
        assert os.path.exists(os.path.join(vdir, "SYSTEM"))
        with open(os.path.join(vdir, "KERNEL.img"), "rb") as f:
            assert f.read() == b"MOCK_KERNEL_BINARY_DATA"
        with open(os.path.join(vdir, "SYSTEM"), "rb") as f:
            assert f.read() == b"MOCK_SYSTEM_SQUASHFS_DATA"

        # Verify version metadata
        with open(os.path.join(vdir, "version.json"), "r", encoding="utf-8") as f:
            v_data = json.load(f)
            assert v_data["tar_file"] == "CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260922221205.tar"
    finally:
        xbmcvfs.File.clear_urls()


def test_os_switcher_tar_import_from_smb_with_delete(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    local_tar = str(tmp_path / "CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260921090828.tar")
    create_dummy_ce_tar(local_tar)

    smb_url = "smb://192.168.1.100/share/CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260921090828.tar"
    xbmcvfs.File.register_url(smb_url, local_tar)

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    try:
        # First yesno: delete tar (True), second yesno: switch now (False)
        with patch("resources.lib.tools.os_switcher.dialog_browse", return_value=smb_url), \
             patch("resources.lib.tools.os_switcher.dialog_input", return_value="21.3-Omega_avdvplus_F10 [09-21 09:08]"), \
             patch("resources.lib.tools.os_switcher.dialog_yesno", side_effect=[True, False]):
            tool._action_import_tar("CoreELEC Version Switcher")

        # smb_url should be deleted from mock
        assert smb_url not in xbmcvfs.File._url_map
        saved = tool._get_saved_versions()
        displays = [s["display_name"] for s in saved]
        assert "21.3-Omega_avdvplus_F10 [09-21 09:08]" in displays
    finally:
        xbmcvfs.File.clear_urls()


def test_os_switcher_tar_import_inaccessible_file(tmp_path):
    tool = OsSwitcherTool(versions_dir=str(tmp_path / "versions"), storage_dir=str(tmp_path / "storage"))

    with patch("resources.lib.tools.os_switcher.dialog_browse", return_value="smb://nonexistent/share/missing.tar"), \
         patch("resources.lib.tools.os_switcher.dialog_ok") as mock_ok:
        tool._action_import_tar("CoreELEC Version Switcher")

    mock_ok.assert_called_once()
    assert "File not accessible" in mock_ok.call_args[0][1]


def test_os_switcher_tar_import_quick_from_update(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    update_dir = str(tmp_path / "storage" / ".update")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)
    os.makedirs(update_dir, exist_ok=True)

    tar_file = os.path.join(update_dir, "CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260922221205.tar")
    create_dummy_ce_tar(tar_file)

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    # dialog_select returns 0 (quick option), dialog_yesno returns False (don't switch now)
    with patch("resources.lib.tools.os_switcher.dialog_select", return_value=0), \
         patch("resources.lib.tools.os_switcher.dialog_input", return_value="21.3-Omega_avdvplus_F10 [09-22 22:12]"), \
         patch("resources.lib.tools.os_switcher.dialog_yesno", return_value=False):
        tool._action_import_tar("CoreELEC Version Switcher")

    saved = tool._get_saved_versions()
    displays = [s["display_name"] for s in saved]
    assert "21.3-Omega_avdvplus_F10 [09-22 22:12]" in displays


def test_os_switcher_tar_import_manual_input(tmp_path):
    flash_dir = str(tmp_path / "flash")
    versions_dir = str(tmp_path / "versions")
    storage_dir = str(tmp_path / "storage")
    os.makedirs(flash_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)
    os.makedirs(storage_dir, exist_ok=True)

    local_tar = str(tmp_path / "CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260922221205.tar")
    create_dummy_ce_tar(local_tar)

    smb_url = "smb://192.168.1.200/share/CoreELEC-Amlogic-no.aarch64-21.3-Omega_avdvplus_F10_20260922221205.tar"
    xbmcvfs.File.register_url(smb_url, local_tar)

    tool = OsSwitcherTool(flash_dir=flash_dir, versions_dir=versions_dir, storage_dir=storage_dir)

    try:
        # dialog_select returns 1 (manual input when no local tars, or 2)
        # First input returns smb_url, second input returns version name
        with patch("resources.lib.tools.os_switcher.dialog_select", return_value=1), \
             patch("resources.lib.tools.os_switcher.dialog_input", side_effect=[smb_url, "21.3-Omega_avdvplus_F10 [09-22 22:12]"]), \
             patch("resources.lib.tools.os_switcher.dialog_yesno", return_value=False):
            tool._action_import_tar("CoreELEC Version Switcher")

        saved = tool._get_saved_versions()
        displays = [s["display_name"] for s in saved]
        assert "21.3-Omega_avdvplus_F10 [09-22 22:12]" in displays
    finally:
        xbmcvfs.File.clear_urls()


def test_os_switcher_tar_import_cancel_menu(tmp_path):
    tool = OsSwitcherTool(versions_dir=str(tmp_path / "versions"), storage_dir=str(tmp_path / "storage"))

    with patch("resources.lib.tools.os_switcher.dialog_select", return_value=-1), \
         patch("resources.lib.tools.os_switcher.dialog_browse") as mock_browse:
        tool._action_import_tar("CoreELEC Version Switcher")

    mock_browse.assert_not_called()


