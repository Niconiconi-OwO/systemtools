# -*- coding: utf-8 -*-
"""Unit tests for kodi_ui helpers."""

from unittest.mock import MagicMock, patch
from resources.lib.common.kodi_ui import dialog_select_details


def test_dialog_select_details_normal():
    items = ["item1", "item2"]
    with patch("xbmcgui.Dialog") as mock_dialog_cls:
        mock_dialog = MagicMock()
        mock_dialog.select.return_value = 1
        mock_dialog_cls.return_value = mock_dialog

        idx = dialog_select_details("Select Tool", items, preselect=0)
        assert idx == 1
        mock_dialog.select.assert_called_once_with("Select Tool", items, preselect=0, useDetails=True)


def test_dialog_select_details_fallback_on_type_error():
    items = ["item1", "item2"]
    with patch("xbmcgui.Dialog") as mock_dialog_cls:
        mock_dialog = MagicMock()

        # Simulate older Kodi that does not accept useDetails keyword argument
        def side_effect(title, items, preselect=-1, **kwargs):
            if "useDetails" in kwargs:
                raise TypeError("select() got an unexpected keyword argument 'useDetails'")
            return 0

        mock_dialog.select.side_effect = side_effect
        mock_dialog_cls.return_value = mock_dialog

        idx = dialog_select_details("Select Tool", items)
        assert idx == 0


def test_dialog_numeric():
    from resources.lib.common.kodi_ui import dialog_numeric
    with patch("xbmcgui.Dialog") as mock_dialog_cls:
        mock_dialog = MagicMock()
        mock_dialog.numeric.return_value = "04:30"
        mock_dialog_cls.return_value = mock_dialog

        val = dialog_numeric(2, "Set Time", default="04:00")
        assert val == "04:30"
        mock_dialog.numeric.assert_called_once_with(2, "Set Time", "04:00")

