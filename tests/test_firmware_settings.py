# -*- coding: utf-8 -*-
"""Unit tests for R10/F10 Firmware Advanced Settings tool."""

import os
import re


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
        "31007", "31008", "31009", "31010", "31011", "31012", "31013",
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

    assert len(CATEGORIES) == 7
    cat_ids = [c["id"] for c in CATEGORIES]
    assert "audio" in cat_ids
    assert "video" in cat_ids
    assert "gui" in cat_ids
    assert "videolibrary" in cat_ids
    assert "network" in cat_ids
    assert "database" in cat_ids
    assert "blurayisocache" in cat_ids

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

    video_settings = get_settings_by_category("video")
    assert len(video_settings) >= 12

