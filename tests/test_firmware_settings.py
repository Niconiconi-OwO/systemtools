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
