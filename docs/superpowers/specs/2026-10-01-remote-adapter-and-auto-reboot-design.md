# 遥控器自动适配与每日自动重启功能设计规范 (Design Spec)

## 一、概述与背景

针对用户在 CoreELEC / 嵌入式播放系统中对于“常用外贸与品牌遥控器开箱即用”以及“长时间运行内存泄漏需定时维护重启”的痛点需求，本项目计划引入两个全新的系统维护工具：
1. **每日自动重启工具 (`AutoRebootTool`)**：基于 systemd timer 实现定时自动重启，配备防死循环保护与原生时间拨盘配置。
2. **遥控器自动适配工具 (`RemoteAdapterTool`)**：为 CoreELEC 适配各类红外 / 蓝牙 / 2.4G 遥控器（分发 keymap、hwdb 及 remote.conf），具备全量自动快照备份、一键撤销还原及出厂配置保护。

针对此前 PR #1 中暴露的高危数据破坏隐患（暴力删除用户现有配置、无备份、全量硬编码中文、零测试用例等），本次设计全面贯彻本项目的架构规范与数据安全准则。

---

## 二、架构设计与工具注册

### 1. 模块组织
新增文件与目录结构如下：
```
resources/
├── data/
│   └── remotes/                     # 11 款遥控器预设配置库（包含 XML, HWDB, CONF, JPG）
│       ├── 6bur02remote/
│       ├── 6bur02R1/
│       ├── zidoov12/
│       ├── zidoov10/
│       ├── g20pro/
│       ├── dune/
│       ├── huaweir22/
│       ├── CMCC2remote/
│       ├── mx3remote/
│       ├── CMBremote/
│       └── aurora4pro/
├── language/
│   ├── resource.language.en_gb/strings.po  # 补全 31400~31599 英文翻译
│   └── resource.language.zh_cn/strings.po  # 补全 31400~31599 中文翻译
└── lib/
    ├── common/
    │   └── kodi_ui.py               # 增加 dialog_numeric 包装函数
    └── tools/
        ├── auto_reboot.py           # AutoRebootTool 实现
        ├── remote_adapter.py        # RemoteAdapterTool 实现
        └── __init__.py              # 导出并注册新工具
```

### 2. 菜单与排序权重 (Order) 规划
为保持主菜单详细对话框与关于页面（`show_about_info`）严格一致，排序权重设定如下：
- `1. OsSwitcherTool` (`order = 10`)
- `2. DtbTool` (`order = 12`)
- `3. RamCleanerTool` (`order = 15`)
- `4. KodiOptimizerTool` (`order = 18`)
- `5. FirmwareSettingsTool` (`order = 19`)
- `6. NetSpeedtestTool` (`order = 20`)
- `7. DiskBenchmarkTool` (`order = 21`)
- `8. NetConfigTool` (`order = 22`)
- **`9. RemoteAdapterTool` (`order = 25`)** —— 放置于网络配置后、日志清理前
- `10. LogCleanerTool` (`order = 30`)
- **`11. AutoRebootTool` (`order = 35`)** —— 放置于清理与维护区末尾

---

## 三、组件 1：每日自动重启 (`AutoRebootTool`) 详细设计

### 1. 类属性与注册
- 类名：`AutoRebootTool(BaseTool)`
- `id = "auto_reboot"`
- `title_id = 31500`（每日自动重启 / Daily Auto Reboot）
- `description_id = 31501`（定时自动重启 CoreELEC / Daily auto reboot via systemd timer）
- `icon = "DefaultPower.png"`
- `order = 35`

### 2. 底层 systemd 文件与机制
- 文件存储路径：`/storage/.config/system.d/`
  - 服务文件：`daily-reboot.service`
  - 定时器文件：`daily-reboot.timer`

- **防死循环安全防护（Uptime 校验）**：
  在 `daily-reboot.service` 的 `ExecStart` 中注入防死循环逻辑：
  ```ini
  [Unit]
  Description=Daily Auto Reboot Service
  After=network-online.target time-sync.target

  [Service]
  Type=oneshot
  ExecStart=/bin/sh -c 'UPTIME=$(cut -d. -f1 /proc/uptime); if [ "$UPTIME" -gt 600 ]; then /usr/sbin/reboot; else echo "Uptime too short (<10m), skipping reboot."; fi'
  ```
  *说明：若系统刚重启开机不足 10 分钟（如重启后系统时钟尚未同步或刚好卡在整点分钟），自动跳过本次重启，杜绝重启死循环。*

- **定时器配置 (`daily-reboot.timer`)**：
  ```ini
  [Unit]
  Description=Daily Auto Reboot Timer

  [Timer]
  OnCalendar=*-*-* {HH:MM}:00
  Persistent=false

  [Install]
  WantedBy=timers.target
  ```

### 3. 用户交互流程
1. **环境检测**：检查 `os_detect.get_system_info().os_type` 是否为 CoreELEC / LibreELEC 或是否存在 `/storage/.config`。非支持环境提示仅支持 CoreELEC 系统。
2. **状态读取**：解析 `daily-reboot.timer` 中的 `OnCalendar` 正则捕获时间，展示“当前状态：[已开启 (每天 HH:MM)]”或“[未开启]”。
3. **主菜单选项**：
   - `1. 设置 / 修改 自动重启时间`
   - `2. 关闭 每日自动重启`
4. **时间输入**：
   - 使用 `kodi_ui.dialog_numeric(2, heading, default_time)` 调起原生 Kodi 时间拨盘。
   - 若用户确认输入有效时间（如 `04:00`），生成 Service 与 Timer 文件，执行：
     - `systemctl daemon-reload`
     - `systemctl enable daily-reboot.timer`
     - `systemctl restart daily-reboot.timer`
   - 弹窗提示设置成功。
5. **停用流程**：
   - 执行 `systemctl stop daily-reboot.timer`、`systemctl disable daily-reboot.timer`。
   - 删除生成的 `.service` 与 `.timer` 文件。
   - 执行 `systemctl daemon-reload` 并弹窗反馈。

---

## 四、组件 2：遥控器自动适配 (`RemoteAdapterTool`) 详细设计

### 1. 类属性与注册
- 类名：`RemoteAdapterTool(BaseTool)`
- `id = "remote_adapter"`
- `title_id = 31408`（遥控器适配工具 / Remote Control Auto-Adapter）
- `description_id = 31409`（为 CoreELEC 适配各种红外/蓝牙/2.4G遥控器 / Adapt various remotes for CoreELEC）
- `icon = "DefaultAddonsInput.png"`
- `order = 25`

### 2. 预设遥控器仓库列表
包含 11 款主流遥控器配置，数据存放于 `resources/data/remotes/{id}/`：
| ID | 名称 (DisplayName) | 适配类型 | 包含文件类型 |
|---|---|---|---|
| `6bur02remote` | AM6B Plus 原厂 UR02 遥控器 | 蓝牙/红外 | .conf, .hwdb, .xml, .jpg |
| `6bur02R1` | AM6B Plus UR02 社区定制配置 | 红外/按键 | .conf, .xml, .jpg |
| `zidoov12` | 芝杜 V12 遥控器 | 蓝牙 | .hwdb, .xml, .jpg |
| `zidoov10` | 芝杜 V10 mini 遥控器 | 蓝牙 | .hwdb, .xml, .jpg |
| `g20pro` | G20 Pro 语音飞鼠遥控器 | 2.4G/红外 | .xml, .jpg |
| `dune` | DUNE 杜恩遥控器 | 蓝牙 | .hwdb, .xml, .jpg |
| `huaweir22` | 华为 R22 遥控器 | 蓝牙 | .hwdb, .xml, .jpg |
| `CMCC2remote` | 中国移动 2.4G 遥控器 (特殊键位版) | 2.4G/红外 | .conf, .hwdb, .xml, .jpg |
| `mx3remote` | MX3 2.4G 飞鼠遥控器 | 2.4G/红外 | .conf, .hwdb, .xml, .jpg |
| `CMBremote` | 中国移动蓝牙遥控器 | 蓝牙/红外 | .conf, .hwdb, .xml, .jpg |
| `aurora4pro` | 腾讯极光 4 Pro 遥控器 | 蓝牙 | .hwdb, .xml |

### 3. 数据安全防御与快照恢复机制 (Snapshot & Restore)
- **绝对不触碰用户的私有 Keymaps**：
  - 严禁删除用户由 Keymap Editor 生成的 `gen.xml` 或手写的 `keyboard.xml`。
  - 所有新映射文件在写入 `special://userdata/keymaps/` 时，必须带有专属前缀：`remote_adapter_gen.xml` / `remote_adapter_keyboard.xml`。
- **自动全量快照 (`/storage/.remote_backup/`)**：
  在执行任何配置部署前，自动创建快照目录 `/storage/.remote_backup/`：
  - 若存在 `/flash/remote.conf`，备份为 `/storage/.remote_backup/remote.conf`。
  - 若存在 `/storage/.config/hwdb.d/*.hwdb`，全量备份到 `/storage/.remote_backup/hwdb.d/`。
  - 若存在 `special://userdata/keymaps/remote_adapter_*.xml`，全量备份。
  - 写入备份元数据 `meta.json` 记录备份时间与原配置摘要。
- **一键撤销还原选项**：
  在遥控器选择列表末尾增加：`[★ 还原上一次的遥控器配置备份]`。
  点击后将备份的文件原样写回各分区，并提醒重启生效，实现 100% 可逆。
- **出厂红外码文件保护**：
  若新适配的遥控器没有 `.conf` 文件：现有的 `/flash/remote.conf` 自动重命名为 `/flash/remote.conf.factory` 保存，严禁物理删除。
- **只读挂载规范与统一重启**：
  - 修改 `/flash` 前使用 `mount -o remount,rw /flash`，修改后在 `finally` 块中使用 `mount -o remount,ro /flash`。
  - 需要重启以应用底层硬件驱动时，统一通过加固的内核级 SysRq / libc 系统调用重启。

---

## 五、国际化 (i18n) 字符串分配表

所有用户界面展示文本全部使用 `get_string(ID)`，统一管理：

### 遥控器适配工具 (`31408 ~ 31440`)
| String ID | en_GB | zh_CN |
|---|---|---|
| 31408 | Remote Control Auto-Adapter | 遥控器适配工具 |
| 31409 | Adapt various IR/Bluetooth/2.4G remotes for CoreELEC | 为 CoreELEC 系统适配各种红外/蓝牙/2.4G遥控器 |
| 31410 | Select Remote to Adapt | 请选择需要适配的遥控器 |
| 31411 | Restore Previous Remote Backup | ★ 还原上一次的遥控器配置备份 |
| 31412 | This feature is only supported on CoreELEC systems. | 未检测到 CoreELEC 环境，此工具仅适用于 CoreELEC！ |
| 31413 | About to adapt remote: [%s]\nExisting configuration will be backed up automatically.\nContinue? | 即将为系统适配：[%s]\n旧配置将被自动安全备份。\n是否继续应用此配置？ |
| 31414 | Remote [%s] applied successfully! Keymaps reloaded. | 【%s】配置已成功应用并实时生效！ |
| 31415 | Hardware driver changes detected for [%s]. A reboot is required to take effect.\nReboot now? | 【%s】底层硬件驱动已写入完成！\n检测到底层配置变更，必须重启才能生效。\n是否立即重启设备？ |
| 31416 | No remote configuration backup found. | 未找到可用的遥控器配置备份。 |
| 31417 | Previous remote backup restored successfully! Reboot now? | 遥控器配置备份已成功还原！是否立即重启设备生效？ |
| 31418 | Failed to apply remote configuration: %s | 遥控器适配执行失败：%s |

### 每日自动重启工具 (`31500 ~ 31530`)
| String ID | en_GB | zh_CN |
|---|---|---|
| 31500 | Daily Auto Reboot | 每日自动重启 |
| 31501 | Set up a systemd timer to reboot CoreELEC daily | 设置系统定时器，让 CoreELEC 每天自动重启释放内存 |
| 31502 | Daily Auto Reboot - Status: %s | 每日自动重启 - 当前状态：%s |
| 31503 | Enabled (Daily at %s) | 已开启 (每天 %s) |
| 31504 | Disabled | 未开启 |
| 31505 | 1. Set / Change Auto Reboot Time | 1. 设置 / 修改 自动重启时间 |
| 31506 | 2. Disable Daily Auto Reboot | 2. 关闭 每日自动重启 |
| 31507 | Set daily auto reboot time: | 请设置每天自动重启的时间： |
| 31508 | Auto reboot configured! System will reboot daily at %s. | 设置成功！系统将在每天 %s 自动执行重启。\n(已开启防死循环保护) |
| 31509 | Daily auto reboot disabled successfully. | 已成功关闭每日自动重启功能。 |
| 31510 | Daily auto reboot is not enabled currently. | 当前未开启自动重启，无需关闭。 |
| 31511 | Failed to configure auto reboot: %s | 自动重启设置失败：%s |

---

## 六、测试与质量保障计划

### 1. `tests/test_auto_reboot.py`
- `test_auto_reboot_system_check`: 验证非 CoreELEC 系统给出提示并优雅退出。
- `test_auto_reboot_get_current_time`: 验证 Timer 文件正规解析及前导 0 补全（如 `4:00` -> `04:00`）。
- `test_auto_reboot_set_timer`: 模拟 `dialog_numeric` 输入时间，验证生成的 `daily-reboot.service` 包含 uptime 校验，验证 `daily-reboot.timer` 正确，验证 systemctl 命令触发。
- `test_auto_reboot_disable_timer`: 验证停用定时器及清理配置文件的流程。

### 2. `tests/test_remote_adapter.py`
- `test_remote_adapter_metadata`: 验证 11 款遥控器元数据完整，对应的数据文件与目录均有效存在。
- `test_remote_adapter_apply_config_safe_xml`: 验证复制 xml 时使用 `remote_adapter_` 安全前缀，用户的 `gen.xml` 和 `keyboard.xml` 完好无损。
- `test_remote_adapter_snapshot_backup`: 验证在适配新遥控器前，现有配置被完整快照备份到 `/storage/.remote_backup/`。
- `test_remote_adapter_restore_backup`: 验证一键还原功能正确恢复之前的配置并删除多余的新文件。
- `test_remote_adapter_factory_conf_protection`: 验证当切换至无 conf 遥控器时，原始 `/flash/remote.conf` 被安全保护（重命名或备份），绝不直接删除。
