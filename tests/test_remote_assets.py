# -*- coding: utf-8 -*-
"""Validation tests for remote control preset assets."""

import os

EXPECTED_REMOTES = [
    "6bur02remote",
    "6bur02R1",
    "zidoov12",
    "zidoov10",
    "g20pro",
    "dune",
    "huaweir22",
    "CMCC2remote",
    "mx3remote",
    "CMBremote",
    "aurora4pro",
]


def test_remote_presets_directory_and_assets():
    base_dir = os.path.join(os.path.dirname(__file__), "..", "resources", "data", "remotes")
    assert os.path.isdir(base_dir), f"Directory {base_dir} does not exist"

    for r_id in EXPECTED_REMOTES:
        r_dir = os.path.join(base_dir, r_id)
        assert os.path.isdir(r_dir), f"Remote directory {r_id} missing"
        files = os.listdir(r_dir)
        assert len(files) > 0, f"Remote directory {r_id} is empty"

        # Each remote must have at least one config file (.xml, .hwdb, or .conf)
        has_config = any(f.endswith((".xml", ".hwdb", ".conf")) for f in files)
        assert has_config, f"Remote {r_id} has no valid config file"
