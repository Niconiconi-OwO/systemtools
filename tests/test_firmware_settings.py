# -*- coding: utf-8 -*-
"""Unit tests for R10/F10 Firmware Advanced Settings tool."""

import os
import re

from resources.lib.tools.firmware_settings import (
    CATEGORIES,
    SETTINGS_SCHEMA,
    get_setting_by_id,
    get_settings_by_category,
)


def test_firmware_settings_i18n_keys():
    """Verify that essential string IDs for firmware settings exist in po files."""
    zh_path = os.path.join("resources", "language", "resource.language.zh_cn", "strings.po")
    en_path = os.path.join("resources", "language", "resource.language.en_gb", "strings.po")

    assert os.path.exists(zh_path), "zh_cn strings.po not found"
    assert os.path.exists(en_path), "en_gb strings.po not found"

    with open(zh_path, "r", encoding="utf-8") as f:
        zh_content = f.read()
    with open(en_path, "r", encoding="utf-8") as f:
        en_content = f.read()

    zh_ids = set(re.findall(r'msgctxt\s+"#(\d+)"', zh_content))
    en_ids = set(re.findall(r'msgctxt\s+"#(\d+)"', en_content))

    # Core required IDs
    required_ids = [
        "31000", "31001", "31002", "31003", "31004", "31005", "31006",
        "31007", "31009", "31010", "31011", "31012", "31013",
        "31014", "31015",
    ]
    for sid in required_ids:
        assert sid in zh_ids, f"ID {sid} missing in zh_cn"
        assert sid in en_ids, f"ID {sid} missing in en_gb"


def test_schema_structure():
    """Verify that CATEGORIES and SETTINGS_SCHEMA are complete and well-formed."""
    from resources.lib.tools.firmware_settings import (
        CATEGORIES,
        SETTINGS_SCHEMA,
        get_setting_by_id,
        get_settings_by_category,
    )

    assert len(CATEGORIES) == 6
    cat_ids = [c["id"] for c in CATEGORIES]
    assert "audio" in cat_ids
    assert "video" in cat_ids
    assert "gui" in cat_ids
    assert "videolibrary" in cat_ids
    assert "network" in cat_ids
    assert "database" in cat_ids
    assert "blurayisocache" not in cat_ids

    # All settings have valid types and default values
    valid_types = {"bool", "choice", "int", "float"}
    assert len(SETTINGS_SCHEMA) >= 30

    for item in SETTINGS_SCHEMA:
        assert item["id"], f"Setting {item} missing id"
        assert item["category"] in cat_ids, f"Setting {item['id']} category not in cat_ids"
        assert item["type"] in valid_types, f"Setting {item['id']} has invalid type {item['type']}"
        assert item["default"] is not None, f"Setting {item['id']} default is None"
        assert "title_id" in item, f"Setting {item['id']} missing title_id"
        assert "desc_id" in item, f"Setting {item['id']} missing desc_id"
        assert "help_id" in item, f"Setting {item['id']} missing help_id"

    # Test lookup functions
    item = get_setting_by_id("subtitleasyncparse")
    assert item is not None
    assert item["section"] == "video"
    assert item["type"] == "bool"
    assert item["default"] == "true"
    assert get_setting_by_id("pagesize") is None

    video_settings = get_settings_by_category("video")
    assert len(video_settings) >= 12


def test_xml_engine_read_write(tmp_path):
    """Test XML read, write, incremental merge, multi-parent tags, backup, and restore."""
    import xml.etree.ElementTree as ET
    from resources.lib.tools.firmware_settings import FirmwareXmlEngine

    userdata = str(tmp_path / "userdata")
    os.makedirs(userdata, exist_ok=True)
    engine = FirmwareXmlEngine(userdata_path=userdata)

    # 1. Read unconfigured setting returns None
    item = get_setting_by_id("subtitleasyncparse")
    val = engine.read_setting_value(item)
    assert val is None

    # 2. Write setting and verify file created
    engine.write_setting_value(item, "true")
    assert os.path.exists(engine.get_xml_path())
    assert engine.read_setting_value(item) == "true"

    # 3. Non-destructive merge: inject an unrelated tag into the file
    as_path = engine.get_xml_path()
    tree = ET.parse(as_path)
    root = tree.getroot()
    net = ET.SubElement(root, "network")
    custom_tag = ET.SubElement(net, "customtag")
    custom_tag.text = "preserved"
    tree.write(as_path, encoding="utf-8")

    # Write another firmware setting
    audio_item = get_setting_by_id("sinksettleholdms")
    engine.write_setting_value(audio_item, "150")

    # Verify customtag is still preserved and new setting updated
    tree2 = ET.parse(as_path)
    root2 = tree2.getroot()
    assert root2.findtext("network/customtag") == "preserved"
    assert root2.findtext("audio/sinksettleholdms") == "150"
    assert root2.findtext("video/subtitleasyncparse") == "true"

    # 4. Multi-parent tags (connecttimeout across 4 database sections)
    db_item = get_setting_by_id("db_connecttimeout")
    engine.write_setting_value(db_item, "8")
    tree3 = ET.parse(as_path)
    root3 = tree3.getroot()
    assert root3.findtext("videodatabase/connecttimeout") == "8"
    assert root3.findtext("musicdatabase/connecttimeout") == "8"
    assert root3.findtext("tvdatabase/connecttimeout") == "8"
    assert root3.findtext("epgdatabase/connecttimeout") == "8"

    # Read back multi-parent value
    assert engine.read_setting_value(db_item) == "8"

    # 5. Backup & restore
    assert engine.has_backup()
    engine.write_setting_value(item, "false")
    assert engine.read_setting_value(item) == "false"
    success = engine.restore_backup()
    assert success is True
    # item should be restored back to "true"
    assert engine.read_setting_value(item) == "true"


def test_firmware_settings_tool_run_view_report(tmp_path):
    """Test viewing status report through FirmwareSettingsTool."""
    from unittest.mock import patch
    from resources.lib.tools.firmware_settings import FirmwareSettingsTool

    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)

    # Main menu options: 0-5 categories, 6: View Status Report, 7: Restore Backup
    # Select 6 (View Status Report), then select -1 (Cancel/Exit)
    with patch("resources.lib.tools.firmware_settings.dialog_select", side_effect=[6, -1]):
        with patch("resources.lib.tools.firmware_settings.dialog_textviewer") as mock_viewer:
            tool.run({})
            mock_viewer.assert_called_once()
            report_text = mock_viewer.call_args[0][1]
            assert "subtitleasyncparse" in report_text


def test_firmware_settings_tool_edit_bool(tmp_path):
    """Test toggling boolean setting value."""
    from resources.lib.tools.firmware_settings import FirmwareSettingsTool

    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)
    item = get_setting_by_id("subtitleasyncparse")

    res = tool._edit_setting_value(item, current_val="false")
    assert res is True
    assert tool.engine.read_setting_value(item) == "true"
    assert tool.has_changes is True


def test_firmware_settings_tool_edit_choice(tmp_path):
    """Test editing choice setting value."""
    from unittest.mock import patch
    from resources.lib.tools.firmware_settings import FirmwareSettingsTool

    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)
    item = get_setting_by_id("asyncfullscreenosd")

    # Select choice index 1 (value "1")
    with patch("resources.lib.tools.firmware_settings.dialog_select", return_value=1):
        res = tool._edit_setting_value(item, current_val="2")
        assert res is True
        assert tool.engine.read_setting_value(item) == "1"


def test_firmware_settings_tool_edit_numeric_validation(tmp_path):
    """Test input validation for numerical settings (range rejection and recovery)."""
    from unittest.mock import patch
    from resources.lib.tools.firmware_settings import FirmwareSettingsTool

    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)
    item = get_setting_by_id("sinksettleholdms")  # range: 0-2000

    # User enters invalid non-numeric, then out of range 9999, then valid 300
    with patch("resources.lib.tools.firmware_settings.dialog_input", side_effect=["invalid", "9999", "300"]):
        with patch("resources.lib.tools.firmware_settings.dialog_ok") as mock_ok:
            res = tool._edit_setting_value(item, current_val="0")
            assert res is True
            assert tool.engine.read_setting_value(item) == "300"
            assert mock_ok.call_count == 2


def test_firmware_settings_tool_reboot_on_exit(tmp_path):
    """Test that tool prompts reboot on exit only when changes were made."""
    from unittest.mock import patch
    from resources.lib.tools.firmware_settings import FirmwareSettingsTool

    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)

    # 1. No changes made, immediately exit (-1)
    with patch("resources.lib.tools.firmware_settings.dialog_select", return_value=-1):
        with patch("resources.lib.tools.firmware_settings.dialog_yesno") as mock_yesno:
            tool.run({})
            mock_yesno.assert_not_called()

    # 2. Changes made, then exit (-1)
    tool.has_changes = True
    with patch("resources.lib.tools.firmware_settings.dialog_select", return_value=-1):
        with patch("resources.lib.tools.firmware_settings.dialog_yesno", return_value=True) as mock_yesno:
            with patch.object(tool, "_do_restart") as mock_restart:
                tool.run({})
                mock_yesno.assert_called_once()
                mock_restart.assert_called_once()





