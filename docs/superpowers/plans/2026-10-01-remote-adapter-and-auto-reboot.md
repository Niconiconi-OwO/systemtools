# 遥控器自动适配与每日自动重启功能实施计划 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为插件规范化引入并实施“每日自动重启”与“遥控器自动适配”两大新工具，建立完备的配置快照备份、一键撤销、出厂红外码保护机制，补齐全量中英国际化与自动化单元测试。

**Architecture:**
- `AutoRebootTool` 采用 systemd timer 实现定时重启，并在 Service 中内置系统运行时间（Uptime > 10m）防死循环保护；
- `RemoteAdapterTool` 实现 11 款主流遥控器配置分发，分发前对当前硬件与按键配置进行全量快照备份（`/storage/.remote_backup/`），支持一键无损撤销还原；
- 遥控器映射部署严禁破坏用户现有 `gen.xml` / `keyboard.xml`，统一采用安全前缀，底层出厂 `remote.conf` 自动重命名为 `.factory` 妥善保存；
- 重启统一联动内核级安全重启机制；所有 UI 文案统一接入 GNU Gettext PO 语言包。

**Tech Stack:** Python 3 (Kodi 19+), systemd timer / service, Linux hwdb, CoreELEC /flash VFAT, Kodi Keymaps XML, pytest.

**Spec:** [docs/superpowers/specs/2026-10-01-remote-adapter-and-auto-reboot-design.md](docs/superpowers/specs/2026-10-01-remote-adapter-and-auto-reboot-design.md)

## Global Constraints

- 严禁硬编码用户界面中英文字符串，所有 UI 文本均须使用 `get_string(string_id)`；
- 严禁静默删除用户现有的 `gen.xml`、`keyboard.xml` 及 `/flash/remote.conf`；
- 所有修改均遵循 TDD 流程：先编写失败单测，再编写实现代码，验证通过后单独提交；
- 必须保持全工程 76+ 个既有单测 100% 通过无回归。

## Review Focus

- **非 CoreELEC 系统安全回退**：在 Android、Windows、Linux 或 macOS 上调用两款工具时，必须友好提示仅支持 CoreELEC 并安全退出，绝不能引发未捕获的路径或命令异常。
- **时间输入合法性与前导 0 格式化**：Kodi `numeric(2, ...)` 返回的时间可能为 `4:00` 或 `04:00`，正则提取与解析必须稳定兼容并统一步长。
- **用户自建 Keymaps 绝对保护**：用户自建的 `gen.xml` 绝不被覆盖或删除，新部署的 XML 必须使用 `remote_adapter_` 前缀。
- **快照备份与一键撤销完备性**：还原备份时能够准确将备份文件放回原位，并清理新释放的映射文件。
- **出厂 `remote.conf` 保护**：适配无红外 conf 的遥控器时，原 `/flash/remote.conf` 必须重命名为 `/flash/remote.conf.factory` 保存，严禁删除。

---

### Task 1: 国际化语言包扩展与 `kodi_ui` 时间拨盘封装

**Files:**
- Modify: `resources/language/resource.language.en_gb/strings.po`
- Modify: `resources/language/resource.language.zh_cn/strings.po`
- Modify: `resources/lib/common/kodi_ui.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_kodi_ui.py`

**Interfaces:**
- Produces: `dialog_numeric(num_type: int, heading: str, default: str = "") -> str` in `kodi_ui.py`
- Produces: String IDs `31408 ~ 31418` (Remote Adapter) and `31500 ~ 31511` (Auto Reboot) in both PO files

- [ ] **Step 1: 在 `tests/conftest.py` 中为 `xbmcgui.Dialog` 添加 `numeric` mock**

确保单元测试运行环境中 `dialog_instance.numeric.return_value = "04:00"`，避免未定义属性。

- [ ] **Step 2: 编写 `dialog_numeric` 的失败单测**

在 `tests/test_kodi_ui.py` 中增加 `test_dialog_numeric()`，测试输入返回值。

- [ ] **Step 3: 运行单测确认失败**

运行：`python -m pytest tests/test_kodi_ui.py -k test_dialog_numeric`
预期：FAIL（`dialog_numeric` 未在 `kodi_ui.py` 中导出）

- [ ] **Step 4: 在 `kodi_ui.py` 中实现 `dialog_numeric` 并扩展双语 PO 文件**

在 `resources/lib/common/kodi_ui.py` 中添加 `dialog_numeric(num_type: int, heading: str, default: str = "") -> str`。
在 `en_gb/strings.po` 和 `zh_cn/strings.po` 中完整写入 spec 中定义的 31408~31418 和 31500~31511 词条。

- [ ] **Step 5: 运行单测确认通过**

运行：`python -m pytest tests/test_kodi_ui.py`
预期：PASS

- [ ] **Step 6: Commit**

```bash
git add resources/language/ resources/lib/common/kodi_ui.py tests/conftest.py tests/test_kodi_ui.py
git commit -m "feat(i18n): add string IDs for remote adapter and auto reboot, add dialog_numeric wrapper"
```

---

### Task 2: 遥控器预设配置资源库引入与校验

**Files:**
- Create: `resources/data/remotes/` 及其 11 个子目录与配置资产（从 pr-1 分支检出）
- Test: `tests/test_remote_assets.py`

**Interfaces:**
- Produces: 11 款遥控器在 `resources/data/remotes/<id>/` 下的配置文件（`remote.conf`, `.hwdb`, `.xml`, `.jpg`）

- [ ] **Step 1: 编写遥控器资源完整性校验测试**

创建 `tests/test_remote_assets.py`，遍历 11 个遥控器 ID，验证每一个目录均存在，且至少包含一个 `.xml` 或 `.hwdb` 或 `.conf` 文件，图片存在时格式合法。

- [ ] **Step 2: 运行测试确认失败**

运行：`python -m pytest tests/test_remote_assets.py`
预期：FAIL（目录 `resources/data/remotes/` 尚不存在）

- [ ] **Step 3: 从 `pr-1` 分支导入 `resources/data/remotes/`**

通过 `git checkout pr-1 -- resources/data/remotes/` 一次性导入预设遥控器资产，验证文件排布。

- [ ] **Step 4: 运行测试确认通过**

运行：`python -m pytest tests/test_remote_assets.py`
预期：PASS

- [ ] **Step 5: Commit**

```bash
git add resources/data/remotes/ tests/test_remote_assets.py
git commit -m "feat(remotes): import preset remote configuration assets for 11 devices"
```

---

### Task 3: 每日自动重启工具 (`AutoRebootTool`) 实现与测试

**Files:**
- Create: `resources/lib/tools/auto_reboot.py`
- Modify: `resources/lib/tools/__init__.py`
- Test: `tests/test_auto_reboot.py`

**Interfaces:**
- Produces: `AutoRebootTool` subclass of `BaseTool`, registered with `id="auto_reboot"`, `order=35`
- Consumes: `dialog_numeric`, `dialog_ok`, `dialog_select`, `get_string` from `kodi_ui.py`; `get_system_info` from `os_detect.py`; `run_command` from `system_exec.py`

- [ ] **Step 1: 编写 `tests/test_auto_reboot.py` 完整测试用例**

覆盖：
1. `test_auto_reboot_non_coreelec_guard`：非 CoreELEC 环境提示并退出；
2. `test_auto_reboot_get_current_time`：解析 timer 格式化时间并补全前导 0；
3. `test_auto_reboot_set_timer_success`：验证生成的 service 文件包含 uptime > 600 防死循环校验、timer 文件正确、systemctl 重新加载；
4. `test_auto_reboot_disable_timer`：验证停止、禁用并清理文件。

- [ ] **Step 2: 运行单测确认失败**

运行：`python -m pytest tests/test_auto_reboot.py`
预期：FAIL（`AutoRebootTool` 未实现）

- [ ] **Step 3: 实现 `resources/lib/tools/auto_reboot.py`**

按照规范实现 `AutoRebootTool`：
- 使用 `get_system_info().os_type` 校验环境；
- 所有交互文案均使用 `get_string`；
- 使用 `dialog_numeric` 输入时间；
- 导出并在 `resources/lib/tools/__init__.py` 注册。

- [ ] **Step 4: 运行单测确认通过**

运行：`python -m pytest tests/test_auto_reboot.py`
预期：PASS

- [ ] **Step 5: Commit**

```bash
git add resources/lib/tools/auto_reboot.py resources/lib/tools/__init__.py tests/test_auto_reboot.py
git commit -m "feat(tools): implement AutoRebootTool with systemd timer and uptime loop guard"
```

---

### Task 4: 遥控器自动适配工具 (`RemoteAdapterTool`) 实现与测试

**Files:**
- Create: `resources/lib/tools/remote_adapter.py`
- Modify: `resources/lib/tools/__init__.py`
- Test: `tests/test_remote_adapter.py`

**Interfaces:**
- Produces: `RemoteAdapterTool` subclass of `BaseTool`, registered with `id="remote_adapter"`, `order=25`
- Consumes: `kodi_ui` dialogs, `os_detect`, `system_exec`, `ctypes`/kernel reboot

- [ ] **Step 1: 编写 `tests/test_remote_adapter.py` 完整测试用例**

覆盖：
1. `test_remote_adapter_safe_xml_copy`：确认复制 xml 到 keymaps 时添加 `remote_adapter_` 前缀，原有 `gen.xml` / `keyboard.xml` 未被删除；
2. `test_remote_adapter_snapshot_backup`：确认部署前旧配置被完整快照备份到 `/storage/.remote_backup/`；
3. `test_remote_adapter_restore_backup`：确认一键还原能够把备份的 conf、hwdb 与 xml 放回原位并清理新增文件；
4. `test_remote_adapter_factory_conf_protection`：当适配无 conf 遥控器时，原始 `/flash/remote.conf` 被重命名为 `.factory` 保护，严禁物理删除；
5. `test_remote_adapter_reboot_dispatch`：确认需要重启时触发硬件/系统重启流程。

- [ ] **Step 2: 运行单测确认失败**

运行：`python -m pytest tests/test_remote_adapter.py`
预期：FAIL（`RemoteAdapterTool` 未实现）

- [ ] **Step 3: 实现 `resources/lib/tools/remote_adapter.py`**

按照安全规范编写 `RemoteAdapterTool`：
- 定义 11 款遥控器元数据表；
- 实现 `_create_backup()` 全量快照与 `_restore_backup()` 一键恢复；
- 实现 `_apply_config()`，安全前缀分发，出厂 conf 保护；
- 遇到重启调用加固的安全重启逻辑；
- 所有交互文案使用 `get_string`；
- 在 `resources/lib/tools/__init__.py` 导出。

- [ ] **Step 4: 运行单测确认通过**

运行：`python -m pytest tests/test_remote_adapter.py`
预期：PASS

- [ ] **Step 5: Commit**

```bash
git add resources/lib/tools/remote_adapter.py resources/lib/tools/__init__.py tests/test_remote_adapter.py
git commit -m "feat(tools): implement RemoteAdapterTool with snapshot backup, restore, and safe keymaps handling"
```

---

### Task 5: 菜单路由整合、关于信息对齐、全量回归与打包校验

**Files:**
- Modify: `resources/lib/router.py`
- Modify: `tests/test_router.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: All 11 registered tools via `ToolRegistry`

- [ ] **Step 1: 更新 `router.py` 中的 `show_about_info` 列表并编写对应测试**

修正 `resources/lib/router.py` 中的 `show_about_info`，使工具序号与 `order` 严格一致（遥控器适配工具为第 9 项，日志清理为第 10 项，每日自动重启为第 11 项）。
在 `tests/test_router.py` 中更新相关断言。

- [ ] **Step 2: 运行全量单元测试**

运行：`python -m pytest tests/`
预期：所有测试全部通过（预期 80+ 个测试用例，100% Passed）。

- [ ] **Step 3: 更新 `README.md` 文档**

在 `README.md` 功能列表中补充遥控器自动适配与每日自动重启的特性介绍与说明。

- [ ] **Step 4: 执行打包脚本验证**

运行：`python scripts/package.py`
验证打包脚本无报错，生成的 ZIP 文件包含新代码与 `resources/data/remotes/` 资产。

- [ ] **Step 5: Commit**

```bash
git add resources/lib/router.py tests/test_router.py README.md
git commit -m "chore: align router menu entries with new tools and update documentation"
```
