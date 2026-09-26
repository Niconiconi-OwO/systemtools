# R10/F10 固件高级设置 (Firmware Settings) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an independent, category-based R10/F10 firmware advanced settings tool in `plugin.program.systemtools` that lists tuning parameters with in-depth technical explanations, allows interactive value modifications with immediate safe XML merging into `advancedsettings.xml`, and prompts for a Kodi reboot upon exit.

**Architecture:** A schema-driven modular tool (`FirmwareSettingsTool` subclassing `BaseTool`) providing 7 functional categories, backed by a dedicated XML engine that performs non-destructive incremental updates and automatic `.bak` backups on `special://userdata/advancedsettings.xml`. All UI text, technical descriptions, and prompts are fully localized via GNU Gettext PO files.

**Tech Stack:** Python 3 (`xbmc.python >= 3.0.0`), `xml.etree.ElementTree`, Kodi GUI API (`xbmcgui.Dialog`), pytest with mock environment.

**Spec:** [docs/superpowers/specs/2026-09-27-r10-f10-firmware-settings-design.md](docs/superpowers/specs/2026-09-27-r10-f10-firmware-settings-design.md)

## Global Constraints

- Target Kodi 19+ (Matrix, Nexus, Omega, Piers) with Python 3.
- Zero hardcoded user-facing strings; all UI text and descriptions must resolve via `get_string(string_id)`.
- Numeric string ID range for this feature: `31000` to `31200`.
- Safe XML manipulation: never overwrite or discard unrelated tags already present in `advancedsettings.xml`.
- Automatic backup creation (`advancedsettings.xml.bak`) prior to first write.
- All code must conform to flake8 and pass all unit tests without actual Kodi runtime dependencies via `tests/conftest.py`.

## Review Focus

1. **Non-destructive XML merge on pre-existing user configurations**: existing custom nodes (e.g. `<network><buffermode>1</buffermode></network>`) must remain untouched when modifying other settings.
2. **Multi-parent database tags**: modifying `connecttimeout` must synchronize all 4 database sections (`<videodatabase>`, `<musicdatabase>`, `<tvdatabase>`, `<epgdatabase>`).
3. **Invalid numerical/out-of-range user input**: inputs violating defined ranges (e.g., negative timeout, float in int field, non-numeric strings) must be rejected gracefully with user warning without modifying XML.
4. **Missing or corrupted XML recovery**: if `advancedsettings.xml` is missing or contains malformed syntax, the engine must safely initialize a clean root without crashing.
5. **Reboot prompt state tracking**: only prompt the user to reboot Kodi on exiting back to the main menu if at least one setting was actually modified during the session.

---

### Task 1: Internationalization Strings (zh_cn & en_gb)

**Files:**
- Modify: `resources/language/resource.language.zh_cn/strings.po`
- Modify: `resources/language/resource.language.en_gb/strings.po`
- Test: `tests/test_i18n.py` (or new validation test)

**Interfaces:**
- Produces: String IDs `31000`–`31150` for tool title, description, category headers, setting names, short summaries, full technical explanations, and UI dialog labels.

- [ ] **Step 1: Write test to verify string IDs exist and match across zh_cn and en_gb**

```python
# In tests/test_firmware_settings.py
def test_firmware_settings_i18n_keys():
    """Verify that all essential string IDs for firmware settings exist in po files."""
    import polib
    zh_po = polib.pofile("resources/language/resource.language.zh_cn/strings.po")
    en_po = polib.pofile("resources/language/resource.language.en_gb/strings.po")

    zh_ids = {e.msgctxt.strip("#") for e in zh_po if e.msgctxt}
    en_ids = {e.msgctxt.strip("#") for e in en_po if e.msgctxt}

    # Core required IDs
    required_ids = ["31000", "31001", "31002", "31003", "31004", "31005", "31006", "31007", "31008"]
    for sid in required_ids:
        assert sid in zh_ids, f"ID {sid} missing in zh_cn"
        assert sid in en_ids, f"ID {sid} missing in en_gb"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_firmware_settings.py::test_firmware_settings_i18n_keys -v`
Expected: FAIL (file or keys missing)

- [ ] **Step 3: Append localized strings to zh_cn and en_gb PO files**

Add msgctxt entries from 31000 to 31150:
- 31000: Tool title ("R10/F10 固件高级设置" / "R10/F10 Firmware Advanced Settings")
- 31001: Tool description ("晶晨 SoC 解码器、ALSA 音频驱动与 Mali GPU 渲染深度调优" / "Advanced tuning for Amlogic SoC, ALSA audio and Mali GPU pipeline")
- 31002-31008: 7 category titles
- 31009: "查看当前配置总览报告" / "View Status Report"
- 31010: "还原备份配置 (.bak)" / "Restore Configurations from Backup (.bak)"
- 31011-31015: Action buttons ("修改数值", "恢复推荐默认值", "返回", "已保存", "配置已变更，是否重启Kodi？")
- 31020-31120: Titles, summaries, and full explanations for all 35+ settings.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_firmware_settings.py::test_firmware_settings_i18n_keys -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add resources/language/ tests/test_firmware_settings.py
git commit -m "feat(i18n): add R10/F10 firmware settings localization strings"
```

---

### Task 2: Firmware Settings Schema & Metadata

**Files:**
- Create: `resources/lib/tools/firmware_settings.py` (Schema definitions)
- Modify: `tests/test_firmware_settings.py`

**Interfaces:**
- Produces:
  - `CATEGORIES: List[Dict[str, Any]]`
  - `SETTINGS_SCHEMA: List[Dict[str, Any]]`
  - `get_setting_by_id(setting_id: str) -> Optional[Dict[str, Any]]`
  - `get_settings_by_category(category_id: str) -> List[Dict[str, Any]]`

- [ ] **Step 1: Write test for schema definitions and lookups**

```python
# In tests/test_firmware_settings.py
from resources.lib.tools.firmware_settings import (
    CATEGORIES,
    SETTINGS_SCHEMA,
    get_setting_by_id,
    get_settings_by_category,
)

def test_schema_structure():
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
    for item in SETTINGS_SCHEMA:
        assert item["id"]
        assert item["category"] in cat_ids
        assert item["type"] in valid_types
        assert item["default"] is not None
        assert "title_id" in item
        assert "desc_id" in item
        assert "help_id" in item

    # Test lookup functions
    item = get_setting_by_id("subtitleasyncparse")
    assert item is not None
    assert item["section"] == "video"
    assert item["type"] == "bool"
    assert item["default"] == "true"

    video_settings = get_settings_by_category("video")
    assert len(video_settings) >= 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_firmware_settings.py::test_schema_structure -v`
Expected: FAIL (cannot import from firmware_settings)

- [ ] **Step 3: Implement Schema in `resources/lib/tools/firmware_settings.py`**

Define `CATEGORIES`, all 35+ items in `SETTINGS_SCHEMA` strictly corresponding to `C:\Users\Mephis\Documents\advancedsettings.xml`, and the helper functions `get_setting_by_id` and `get_settings_by_category`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_firmware_settings.py::test_schema_structure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add resources/lib/tools/firmware_settings.py tests/test_firmware_settings.py
git commit -m "feat(firmware_settings): define schema and metadata for R10/F10 parameters"
```

---

### Task 3: XML Engine (Read, Safe Merge, Write, Backup, Restore)

**Files:**
- Modify: `resources/lib/tools/firmware_settings.py`
- Modify: `tests/test_firmware_settings.py`

**Interfaces:**
- Produces:
  - `FirmwareXmlEngine(userdata_path: str)`:
    - `get_xml_path() -> str`
    - `read_setting_value(item: Dict[str, Any]) -> str`
    - `write_setting_value(item: Dict[str, Any], new_value: str) -> None`
    - `backup_config() -> Optional[str]`
    - `restore_backup() -> bool`
    - `has_backup() -> bool`
    - `get_all_status() -> List[Tuple[Dict[str, Any], str]]`

- [ ] **Step 1: Write comprehensive XML engine tests**

```python
# In tests/test_firmware_settings.py
def test_xml_engine_read_write(tmp_path):
    userdata = str(tmp_path / "userdata")
    os.makedirs(userdata, exist_ok=True)
    engine = FirmwareXmlEngine(userdata_path=userdata)

    # 1. Read unconfigured setting returns None or default indicator
    item = get_setting_by_id("subtitleasyncparse")
    val = engine.read_setting_value(item)
    assert val is None

    # 2. Write setting and verify file created and backup created
    engine.write_setting_value(item, "true")
    assert os.path.exists(engine.get_xml_path())
    assert engine.read_setting_value(item) == "true"

    # 3. Non-destructive merge: inject an unrelated tag
    as_path = engine.get_xml_path()
    tree = ET.parse(as_path)
    root = tree.getroot()
    net = ET.SubElement(root, "network")
    custom_tag = ET.SubElement(net, "customtag")
    custom_tag.text = "preserved"
    tree.write(as_path)

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

    # 5. Backup & restore
    assert engine.has_backup()
    engine.write_setting_value(audio_item, "500")
    assert engine.read_setting_value(audio_item) == "500"
    success = engine.restore_backup()
    assert success is True
    # audio item should be restored back
    assert engine.read_setting_value(audio_item) == "150"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_firmware_settings.py::test_xml_engine_read_write -v`
Expected: FAIL (FirmwareXmlEngine not implemented)

- [ ] **Step 3: Implement `FirmwareXmlEngine` in `resources/lib/tools/firmware_settings.py`**

Implement XML parsing, safe multi-parent handling, `.bak` backup creation, restoration, and indentation formatting using `xml.etree.ElementTree`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_firmware_settings.py::test_xml_engine_read_write -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add resources/lib/tools/firmware_settings.py tests/test_firmware_settings.py
git commit -m "feat(firmware_settings): implement XML safe merge engine and backup manager"
```

---

### Task 4: UI Flow & Dialog Interactions (`FirmwareSettingsTool`)

**Files:**
- Modify: `resources/lib/tools/firmware_settings.py`
- Modify: `tests/test_firmware_settings.py`

**Interfaces:**
- Produces:
  - `FirmwareSettingsTool(BaseTool)`
    - `id = "firmware_settings"`
    - `title_id = 31000`
    - `description_id = 31001`
    - `order = 17`
    - `run(params: Dict[str, str]) -> None`
    - `_show_category_menu() -> None`
    - `_show_settings_in_category(category_id: str) -> None`
    - `_show_setting_detail(item: Dict[str, Any]) -> None`
    - `_edit_setting_value(item: Dict[str, Any], current_val: Optional[str]) -> bool`
    - `_show_status_report() -> None`
    - `_restore_backup_dialog() -> None`

- [ ] **Step 1: Write unit tests for tool menu navigation and editing**

```python
# In tests/test_firmware_settings.py
from unittest.mock import patch

def test_firmware_settings_tool_run_view_report(tmp_path):
    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)

    # Mock dialog_select to choose "View Status Report" (index 7) then Cancel (-1)
    with patch("resources.lib.tools.firmware_settings.dialog_select", side_effect=[7, -1]):
        with patch("resources.lib.tools.firmware_settings.dialog_textviewer") as mock_viewer:
            tool.run({})
            mock_viewer.assert_called_once()


def test_firmware_settings_tool_edit_bool(tmp_path):
    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)
    item = get_setting_by_id("subtitleasyncparse")

    # Test toggling boolean
    res = tool._edit_setting_value(item, current_val="false")
    assert res is True
    assert tool.engine.read_setting_value(item) == "true"


def test_firmware_settings_tool_edit_choice(tmp_path):
    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)
    item = get_setting_by_id("asyncfullscreenosd")

    # Select choice index 1 (value: "1")
    with patch("resources.lib.tools.firmware_settings.dialog_select", return_value=1):
        res = tool._edit_setting_value(item, current_val="2")
        assert res is True
        assert tool.engine.read_setting_value(item) == "1"


def test_firmware_settings_tool_edit_numeric_validation(tmp_path):
    userdata = str(tmp_path / "userdata")
    tool = FirmwareSettingsTool(userdata_path=userdata)
    item = get_setting_by_id("sinksettleholdms")  # range: 0-2000

    # User enters invalid string then out of range number then valid number
    with patch("resources.lib.tools.firmware_settings.dialog_input", side_effect=["invalid", "9999", "300"]):
        with patch("resources.lib.tools.firmware_settings.dialog_ok") as mock_ok:
            res = tool._edit_setting_value(item, current_val="0")
            assert res is True
            assert tool.engine.read_setting_value(item) == "300"
            assert mock_ok.call_count == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_firmware_settings.py::test_firmware_settings_tool_run_view_report -v`
Expected: FAIL (FirmwareSettingsTool not found)

- [ ] **Step 3: Implement `FirmwareSettingsTool` in `resources/lib/tools/firmware_settings.py`**

Implement complete dialog flows, detailed view with full technical explanations, input validation for `int`/`float`, `choice` single select, `bool` toggle, status report generation, and exit reboot prompt tracking.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_firmware_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add resources/lib/tools/firmware_settings.py tests/test_firmware_settings.py
git commit -m "feat(firmware_settings): implement interactive dialogs and validation flow"
```

---

### Task 5: Register Tool & Export in `__init__.py`

**Files:**
- Modify: `resources/lib/tools/__init__.py`
- Modify: `resources/lib/tools/firmware_settings.py` (ensure `@ToolRegistry.register` decorator)
- Test: `tests/test_router.py`

- [ ] **Step 1: Write test to verify `firmware_settings` is registered in ToolRegistry**

```python
# In tests/test_router.py
def test_firmware_settings_registered():
    from resources.lib.tools.base_tool import ToolRegistry
    tool_cls = ToolRegistry.get("firmware_settings")
    assert tool_cls is not None
    assert tool_cls.id == "firmware_settings"
    assert tool_cls.order == 17
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_router.py::test_firmware_settings_registered -v`
Expected: FAIL (tool not found in registry)

- [ ] **Step 3: Update `resources/lib/tools/__init__.py`**

Import and export `FirmwareSettingsTool` in `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_router.py::test_firmware_settings_registered -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add resources/lib/tools/__init__.py tests/test_router.py
git commit -m "feat(firmware_settings): register and export FirmwareSettingsTool in ToolRegistry"
```

---

### Task 6: Full Suite Verification & Code Quality

**Files:**
- Test all files in `tests/`
- Check code style with `flake8`

- [ ] **Step 1: Run all unit tests with pytest**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS with 0 failures

- [ ] **Step 2: Run flake8 lint check**

Run: `flake8 resources/ addon.py tests/`
Expected: Clean output with 0 lint violations

- [ ] **Step 3: Test packaging**

Run: `python scripts/package.py`
Expected: ZIP bundle generated in `dist/` successfully

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "chore(release): finalize R10/F10 firmware settings tool"
```
