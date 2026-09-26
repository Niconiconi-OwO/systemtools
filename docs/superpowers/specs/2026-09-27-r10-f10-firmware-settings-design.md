# R10/F10 固件高级设置 (Firmware Settings) 设计规范

## 1. 概述与背景

CoreELEC / Amlogic 定制固件（如 CPM R10、F10 等）针对晶晨 SoC 硬件解码器、ALSA 音频驱动、Mali GPU EGL 渲染管线以及蓝光播放机制引入了多项专用的底层调优参数。

本设计旨在将 `advancedsettings.xml` 中的所有 R10/F10 固件专项优化参数以独立工具模块的形式整合进 `plugin.program.systemtools`（系统工具箱）。

### 核心设计原则
1. **不预设死板档位**：不采用一揽子一键覆盖的预设包，而是清晰罗列所有配置项及其深度原理解析，尊重用户对底层行为的掌控。
2. **分类分级呈现**：按 7 大系统模块分类呈现，每项展示“当前值”与“核心功能简述”。
3. **点击查看原理解析与即时修改**：点击配置项弹出详细原理说明（含问题场景、解决方式与推荐建议），并支持直接修改或一键恢复默认。
4. **实时保存与无损合并**：参数修改后自动执行安全增量合并写入 `userdata/advancedsettings.xml`，不破坏用户原有的其它自定义 XML 节点，且在首次修改前自动生成 `.bak` 备份。
5. **退出提示重启**：返回主菜单时若检测到配置变更，统一友好询问是否重启 Kodi 使底层参数生效。

---

## 2. 数据模型与 Schema 规范

在 `resources/lib/tools/firmware_settings.py` 中以声明式 Schema 定义全部 7 大分类及共 30+ 项参数元数据。

每个配置项的 Schema 结构定义如下：
```python
{
    "id": "subtitleasyncparse",
    "section": "video",          # XML 父节点，或元组 ("videodatabase", "musicdatabase", ...)
    "tag": "subtitleasyncparse", # XML 标签名
    "type": "bool",              # "bool" | "choice" | "int" | "float"
    "default": "true",           # 固件默认推荐值
    "title_id": 31010,           # 简明标题多语言 ID
    "desc_id": 31011,            # 列表单行摘要多语言 ID
    "help_id": 31012,            # 完整原理解析多语言 ID
    "choices": [...],            # 若为 choice 类型，可选值及显示文案列表
    "range": (min_val, max_val), # 若为 int/float 类型，合法取值区间
    "unit": "",                  # 单位（如 "ms", "s", "MB", "FPS"）
}
```

### 7 大功能模块与设置项明细

#### 分类 1：音频引擎与 ALSA 输出 (Audio Engine & ALSA Sink)
- **`pcmsinkbitsmax`** (`<audio><pcmsinkbitsmax>`):
  - 类型：`choice` (0, 16, 24, 32)，默认：`0`。
  - 说明：PCM 最大位深限制。针对非源码透传（PCM 输出）时，若外部 DAC/功放与 32bit 握手异常或出现爆音，可限制为 16 或 24。
- **`sinksettleholdms`** (`<audio><sinksettleholdms>`):
  - 类型：`int`，范围：`0-2000` ms，默认：`0`。
  - 说明：音频输出初始化静音保持时间。在切换音频格式/采样率时静音指定时间，消除功放/回音壁锁定时钟瞬间的“噼啪”爆音。

#### 分类 2：视频播放与硬件解码 (Video Player & Codec)
- **`menudomainqueuetimesize`** (`<video><menudomainqueuetimesize>`):
  - 类型：`float`，范围：`0.0-16.0` s，默认：`1.0`。
  - 说明：蓝光/DVD 交互菜单域数据缓冲队列时长。增大该值可有效避免播放原盘导航菜单时的卡顿与加载延迟。
- **`bdboundarydrain`** (`<video><bdboundarydrain>`):
  - 类型：`bool`，默认：`true`。
  - 说明：蓝光无缝分段跨片段边界排空缓冲。在分段跳转时排空旧解码缓冲，防止多版本/分段蓝光跨 m2ts 衔接处音画不同步或马赛克。
- **`subtitleasyncparse`** (`<video><subtitleasyncparse>`):
  - 类型：`bool`，默认：`true`。
  - 说明：异步字幕解析。将 ASS/SSA 复杂特效字幕和 PGS 图形字幕解析移至后台工作线程，消除加载字幕瞬间的掉帧微卡。
- **`asyncfullscreenosd`** (`<video><asyncfullscreenosd>`):
  - 类型：`choice` (0: 禁用, 1: 强制开启, 2: 自动/仅全屏视频活动时开启)，默认：`2`。
  - 说明：全屏 OSD 异步渲染模式。将全屏播放时的进度条、信息面板等 OSD 渲染与主视频播放解耦，大幅提升 OSD 弹出与滑动流畅度。
- **`asyncvideolayerrender`** (`<video><asyncvideolayerrender>`):
  - 类型：`bool`，默认：`true`。
  - 说明：异步视频图层渲染。默认开启；若在新版固件遇到特效字幕闪烁，设为 false 可解决。
- **`seekminimumdistancebeforeeof`** (`<video><seekminimumdistancebeforeeof>`):
  - 类型：`int`，范围：`0-600` s，默认：`10`。
  - 说明：文件末尾最小 Seek 安全距离。防止快进/跳转过于靠近片尾时直接触发意外退出或连播下一个视频。
- **`dvvsvdbv1`** (`<video><dvvsvdbv1>`):
  - 类型：`bool`，默认：`false`。
  - 说明：强制使用 Dolby Vision VSVDB V1 数据块。默认使用标准的 V2 格式；连接极老款仅支持 V1 规范的杜比视界电视/投影仪时可设为 true。
- **`deinterlacedelaycompensation`** (`<video><deinterlacedelaycompensation>`):
  - 类型：`bool`，默认：`false`。
  - 说明：隔行扫描硬件反交错延迟补偿。针对 50i/60i 反交错流，自动补偿硬件 Deinterlacer 带来的 1~2 场时钟延迟以保证唇音同步。
- **`videoratefieldhold`** (`<video><videoratefieldhold>`):
  - 类型：`bool`，默认：`true`。
  - 说明：视频场频保持。播放隔行/逐行交替片源时抑制过快的刷新率反复切换，避免电视黑屏闪烁。
- **`vc1forceframeint`** (`<video><vc1forceframeint>`):
  - 类型：`bool`，默认：`true`。
  - 说明：VC-1 Amlogic 硬件解码优化。自动区分逐行与隔行并写入驱动 (`/sys/module/amvdec_vc1/parameters/force_frame_int`)，彻底根治晶晨芯片 VC-1 播放卡顿与绿屏。
- **`vc1dropframe`** (`<video><vc1dropframe>`):
  - 类型：`bool`，默认：`true`。
  - 说明：VC-1 坏帧丢弃机制。遇到损坏或时间戳错乱的 VC-1 帧允许解码器丢帧恢复，防止解码器死锁假死。
- **`vc1repairtimestamps`** (`<video><vc1repairtimestamps>`):
  - 类型：`bool`，默认：`true`。
  - 说明：VC-1 时间戳自动修复。对 PTS/DTS 时间戳抖动不平整的片源进行重校准，保证 23.976fps 流畅播放。

#### 分类 3：GUI 渲染与 Mali 绘图管线 (GUI & Mali EGL Pipeline)
- **`bufferagepartialredraw`** (`<gui><bufferagepartialredraw>`):
  - 类型：`choice` (0: 关闭/全屏重绘, 1: 开启局部脏区重绘)，默认：`1`。
  - 说明：基于 EGL Buffer Age 的局部重绘。大幅减轻 Amlogic Mali GPU 渲染负担，显著降低发热并提升操作跟手度。
- **`bufferageafterrenderscope`** (`<gui><bufferageafterrenderscope>`):
  - 类型：`bool`，默认：`true`。
  - 说明：渲染作用域结束后更新 Buffer Age 跟踪。
- **`maxdirtyregions`** (`<gui><maxdirtyregions>`):
  - 类型：`int`，范围：`0-64`，默认：`4`。
  - 说明：最大独立脏区跟踪矩形数。超过该数量时合并为单一外接大包围盒，平衡 CPU 碰撞计算与 GPU 绘制开销。
- **`skipsleepactivewindow`** (`<gui><skipsleepactivewindow>`):
  - 类型：`int`，范围：`0-2000` ms，默认：`250`。
  - 说明：交互后跳过休眠的活动窗口时间。用户按键或滑动列表后的指定时间内不限速，保证界面即时丝滑响应。
- **`menuidleframeratecap`** (`<gui><menuidleframeratecap>`):
  - 类型：`int`，范围：`0-60` FPS (0=跟随屏幕刷新率)，默认：`0`。
  - 说明：菜单静止/空闲时的帧率上限。可在界面停顿不动时大幅降低功耗与温度。
- **`skinhdrfbo`** (`<gui><skinhdrfbo>`):
  - 类型：`choice` (0: 关闭, 1: 开启)，默认：`0`。
  - 说明：皮肤 HDR 帧缓冲渲染。允许 Kodi 皮肤直接在 HDR FBO 中以宽色域渲染（实验性）。
- **`osdguestcomposite`** (`<gui><osdguestcomposite>`):
  - 类型：`choice` (0: 默认, 1: 开启)，默认：`0`。
  - 说明：OSD 客制化合成模式。
- **`osdtrace`** (`<gui><osdtrace>`):
  - 类型：`choice` (0: 关闭, 1: 开启)，默认：`0`。
  - 说明：OSD 脏区调试跟踪。
- **`anisotropicfiltering`** (`<gui><anisotropicfiltering>`):
  - 类型：`choice` (0: 关闭, 2: 2x, 4: 4x, 8: 8x, 16: 16x)，默认：`0`。
  - 说明：GUI 材质各向异性过滤。提升倾斜视角或 3D 视图中皮肤海报和文字的清晰度。
- **`fronttobackrendering`** (`<gui><fronttobackrendering>`):
  - 类型：`bool`，默认：`false`。
  - 说明：Front-to-Back 渲染排序。配合早期深度测试减少透明/不透明图层之间的 Overdraw 覆写开销。
- **`geometryclear`** (`<gui><geometryclear>`):
  - 类型：`bool`，默认：`true`。
  - 说明：帧交换前清空几何体缓冲。
- **`waitvsyncbeforeswap`** (`<gui><waitvsyncbeforeswap>`):
  - 类型：`bool`，默认：`true`。
  - 说明：交换前后缓冲前等待垂直同步。防止界面滑动撕裂，提供平滑 VSync 锁定。
- **`waitgpubeforeswap`** (`<gui><waitgpubeforeswap>`):
  - 类型：`choice` (0: 不等待, 1: 始终等待, 2: 仅全屏视频播放时等待)，默认：`2`。
  - 说明：帧交换前等待 GPU 执行完毕。保证全屏播放下视频平面与界面字幕/OSD 刷新步调严格一致。
- **`srgbhdrcomposite`** (`<gui><srgbhdrcomposite>`):
  - 类型：`bool`，默认：`true`。
  - 说明：sRGB 色彩校正混合。避免 SDR 皮肤界面在覆盖于 HDR / Dolby Vision 视频上方时产生色彩过饱和与刺眼过曝。
- **`compositedither`** (`<gui><compositedither>`):
  - 类型：`bool`，默认：`true`。
  - 说明：界面合成抖动抗色带处理。消除暗色渐变背景和半透明浮层上的阶梯色彩断层。
- **`asynctextureupload`** (`<gui><asynctextureupload>`):
  - 类型：`bool`，默认：`true`。
  - 说明：异步材质上传 PBO。使用 Pixel Buffer Object 在后台上传海报缩略图，杜绝快速翻页时的微顿卡。
- **`mipmapping`** (`<gui><mipmapping>`):
  - 类型：`bool`，默认：`false`。
  - 说明：皮肤纹理 Mipmapping 多级渐远纹理。
- **`mipmappingsharpen`** (`<gui><mipmappingsharpen>`):
  - 类型：`float`，范围：`0.0-3.0`，默认：`0.5`。
  - 说明：Mipmap 锐化偏差值。负向 LOD 偏移，改善微缩图标的清晰锐利度。
- **`minifiedmipmapping`** (`<gui><minifiedmipmapping>`):
  - 类型：`bool`，默认：`true`。
  - 说明：仅针对缩小显示的纹理生成 Mipmap。节省显存占用。

#### 分类 4：媒体库管理 (Video Library)
- **`casesensitivelocalartmatch`** (`<videolibrary><casesensitivelocalartmatch>`):
  - 类型：`bool`，默认：`true`。
  - 说明：本地同名封面/海报是否区分大小写。若挂载 Linux/NAS/SMB 共享中混有 Poster.JPG 与 poster.jpg，设为 false 可避免搜刮漏图。

#### 分类 5：局域网与网络协议 (Network & NFS)
- **`nfstimeout`** (`<network><nfstimeout>`):
  - 类型：`int`，范围：`0-3600` s，默认：`0`。
  - 说明：NFS 连接超时时间。
- **`nfsretries`** (`<network><nfsretries>`):
  - 类型：`int`，范围：`-1-30` (-1 表示系统默认)，默认：`-1`。
  - 说明：NFS 连接重试次数。

#### 分类 6：远程数据库超时保护 (Database Connect)
- **`connecttimeout`** (同时映射 `<videodatabase>`, `<musicdatabase>`, `<tvdatabase>`, `<epgdatabase>` 的 `<connecttimeout>`):
  - 类型：`int`，范围：`1-60` s，默认：`5`。
  - 说明：远程 MySQL/MariaDB 连接超时保护。防止 NAS 睡眠或网络异常时 Kodi 启动死锁卡在黑屏或 Splash 界面。

#### 分类 7：蓝光 ISO 块缓存 (Blu-ray ISO Cache)
- **`pagesize`** (`<blurayisocache><pagesize>`):
  - 类型：`int`，默认：`262144` (256 KB)。
  - 说明：蓝光 ISO 缓存页大小（字节）。
- **`maxbytes`** (`<blurayisocache><maxbytes>`):
  - 类型：`int`，默认：`67108864` (64 MB)。
  - 说明：最大内存缓存限制（字节）。
- **`forwardprefetchpages`** (`<blurayisocache><forwardprefetchpages>`):
  - 类型：`int`，范围：`0-16`，默认：`1`。
  - 说明：顺序读取预读页数。
  - *注：R10 引入；F10 及更高版本已内化为 LRU 机制。*

---

## 3. 用户交互流程设计 (UI Flow)

### 3.1 主入口分类菜单
用户从插件主菜单选择“R10/F10 固件高级设置”进入：
- 1. 音频引擎与输出 (Audio & ALSA Sink) `[2 项]`
- 2. 视频播放与硬件解码 (Video & Codec) `[12 项]`
- 3. GUI 渲染与 Mali 绘图管线 (GUI & Mali EGL) `[19 项]`
- 4. 媒体库管理 (Video Library) `[1 项]`
- 5. 局域网协议 (Network & NFS) `[2 项]`
- 6. 远程数据库超时保护 (Database Connect) `[1 项]`
- 7. 蓝光 ISO 块缓存 (Blu-ray ISO Cache) `[3 项]`
- 8. 查看当前配置总览报告 (View Status Report)
- 9. 还原备份配置 (Restore from .bak)

### 3.2 分类下设置项列表展示
进入特定分类后，弹出列表对话框，每一项显示：
`[序号] [状态/当前值] 配置项名称 - 简要功效`
例如：
- `1. [0 (默认)] PCM 最大位深限制 - 解决外部DAC握手爆音`
- `2. [开启] 异步字幕解析 - 将复杂字幕移至后台，消除掉帧`
- `3. [自动(2)] 全屏 OSD 异步渲染 - 解耦 OSD 与主视频`

### 3.3 设置项详情与修改
用户点击列表中的某一项后，弹出详情窗口（`dialog_select` 或说明+操作），内容：
- **标题**：`设置名称 (标签路径)`
- **状态比对**：`当前生效值: X | 推荐默认值: Y`
- **详细原理解析**：原汁原味展示原 XML 注释中的背景与功效。
- **操作项**：
  - `1. 修改数值 (Modify Value)`
  - `2. 恢复推荐默认值 (Reset to Recommended)`
  - `3. 返回 (Back)`

### 3.4 交互修改控件
- **`bool` 开关**：点击后直接反转（True ↔ False），无需额外确认；
- **`choice` 单选**：弹出选项单选框（如 0: 禁用, 1: 强制开启, 2: 自动）；
- **`int`/`float` 数值**：弹出 Kodi 原生数值输入框 `dialog_numeric` / `dialog_keyboard`，带合法范围提示与校验；若输入超出范围，弹出 `dialog_ok` 提醒并保持原值。

### 3.5 实时安全保存与重启确认
1. 用户每次确认修改某个值后，底层立即调用 XML 合并逻辑安全更新 `special://userdata/advancedsettings.xml`。
2. 弹出 Kodi 顶部轻量浮窗通知（`show_notification`）：`已保存: <tag> = <value>`。
3. 记录本次会话内是否有修改标记 `has_changes = True`。
4. 当用户最终逐级退出固件设置工具、返回主菜单时：
   若 `has_changes == True`，弹出 `dialog_yesno` 询问：
   `“检测到高级设置已修改并保存。需要重启 Kodi 以生效配置，是否立即重启？”`
   若用户点击“是”，调用系统的 `reboot_system` 执行平稳重启；若点击“否”，则正常返回。

---

## 4. XML 增量读写与备份机制

### 4.1 读取与解析
1. 定位 `userdata_dir = get_default_userdata_dir()`，配置文件目标路径为 `userdata_dir/advancedsettings.xml`。
2. 若文件存在，使用 `xml.etree.ElementTree` 解析；若文件不存在，新建根节点 `<advancedsettings>`。
3. 读取配置项时：
   - 沿指定的父节点路径查找对应子标签（如 `video` -> `subtitleasyncparse`）；
   - 若标签存在且有值，去除空白后返回；
   - 若未找到标签，返回 `"未设置 (使用系统默认)"`，同时内部标记为未配置。

### 4.2 增量合并与写入
1. 修改前检查 `advancedsettings.xml.bak` 是否存在；若不存在，克隆一份作为初始备份。
2. 根据配置项的 `section`：
   - 若 `section` 为字符串（如 `"video"`），查找 `<video>`，若不存在则调用 `ET.SubElement(root, "video")`；
   - 在该父节点下查找 `<tag>`，若不存在则创建，将其 `.text` 设置为目标字符串；
   - 若 `section` 为元组列表（如数据库超时四个标签），循环对所有父节点应用相同更新。
3. 调用 `ET.indent(root, space="  ")` 进行美化排版。
4. 使用 `utf-8` 编码及 `xml_declaration=True` 保存写入目标文件。
5. **绝对保证**：不触碰未在当前操作中的任何已有 XML 节点和注释。

### 4.3 配置还原
提供“还原备份配置”：
1. 检查是否存在 `advancedsettings.xml.bak`。
2. 若存在，复制覆盖回 `advancedsettings.xml`。
3. 弹出成功提示并询问是否立即重启 Kodi。

---

## 5. 国际化 (i18n) 与代码架构

### 5.1 模块与文件清单
- **核心逻辑**：[resources/lib/tools/firmware_settings.py](resources/lib/tools/firmware_settings.py)
- **工具导出**：[resources/lib/tools/__init__.py](resources/lib/tools/__init__.py)
- **语言文案**：
  - 中文：[resources/language/resource.language.zh_cn/strings.po](resources/language/resource.language.zh_cn/strings.po) (ID 区间: 31000 - 31200)
  - 英文：[resources/language/resource.language.en_gb/strings.po](resources/language/resource.language.en_gb/strings.po) (ID 区间: 31000 - 31200)
- **单元测试**：[tests/test_firmware_settings.py](tests/test_firmware_settings.py)

### 5.2 命名与主菜单注册
- `id = "firmware_settings"`
- `title_id = 31000` (R10/F10 固件高级设置 / R10/F10 Firmware Advanced Settings)
- `description_id = 31001` (晶晨 SoC 晶晨驱动、Mali GPU 渲染管线与蓝光缓存高级调优 / Advanced tuning for Amlogic SoC, Mali GPU pipeline and Blu-ray cache)
- `icon = "DefaultAddonProgram.png"`
- `order = 17`

---

## 6. 测试与验证策略

1. **Schema 校验测试**：
   - 验证所有 Schema 定义中的字段完整性（tag、section、type、default 等非空合法）。
2. **XML 增量更新与保留性测试**：
   - 测试全新生成 `advancedsettings.xml`。
   - 测试更新已存在节点的值。
   - 测试更新一个分类时，不会改变另一个已有自定义分类节点的内容（如自定义 `<network><buffermode>`）。
   - 测试多父节点映射（数据库超时 4 个 tag 同时正确写入）。
3. **参数校验与类型转换测试**：
   - 测试布尔值反转。
   - 测试合法数值范围写入与越界拦截。
   - 测试枚举单选值切换。
4. **备份与还原测试**：
   - 测试 `.bak` 文件在初次修改时正确创建。
   - 测试还原功能正确恢复初始内容。
5. **pytest 离线全量通过**：
   - 依赖 `tests/conftest.py` Kodi Mocks 确保在标准 Python 虚拟环境中执行 `python -m pytest tests/` 通过。
