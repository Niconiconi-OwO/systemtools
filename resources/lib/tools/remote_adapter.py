# -*- coding: utf-8 -*-
"""Tool: CoreELEC Remote Control Auto-Adapter and Keymap Switcher."""

import os
import xbmc
import xbmcvfs
import traceback
import xbmcgui
from typing import Dict

from ..common.kodi_ui import (
    dialog_ok,
    dialog_select,
    dialog_yesno,
    get_string,
    show_notification,
)
from ..common.logger import debug, error, info
from ..common.system_exec import run_command
from .base_tool import BaseTool, ToolRegistry


@ToolRegistry.register
class RemoteAdapterTool(BaseTool):
    # 按照标准规范定义的类属性
    id = "remote_adapter"
    title_id = 31408        # 菜单标题字符串ID
    description_id = 31409  # 描述字符串ID
    icon = "DefaultAddonsInput.png"
    order = 25              # 排序权重，放在DTB工具后面

    # 11款遥控器配置列表
    REMOTES = [
        {"id": "6bur02remote", "name": "am6b plus UR02遥控器"},
        {"id": "6bur02R1",     "name": "am6b plus UR02群友“别伍”配置"},
        {"id": "zidoov12",     "name": "芝杜V12遥控器"},
        {"id": "zidoov10",     "name": "芝杜V10 mini遥控器"},
        {"id": "g20pro",       "name": "G20pro遥控器"},
        {"id": "dune",         "name": "DUNE杜恩遥控器"},
        {"id": "huaweir22",    "name": "华为R22遥控器"},
        {"id": "CMCC2remote",  "name": "中国移动遥控器2.4G (确认键无效版)"},
        {"id": "mx3remote",    "name": "MX3 2.4G遥控器"},
        {"id": "CMBremote",    "name": "中国移动蓝牙遥控器 (确认键可用版)"},
        {"id": "aurora4pro",   "name": "腾讯极光4pro遥控器"}
    ]

    def run(self, params: Dict[str, str]) -> None:
        """主入口：用户在菜单点击此工具时执行"""
        title = get_string(self.title_id, "遥控器适配工具")
        info("Remote Adapter Tool invoked")

        # 1. 检查是否为 CoreELEC 环境
        if not os.path.exists("/storage/.config"):
            dialog_ok(title, "未检测到 CoreELEC 系统环境，此工具仅适用于 CoreELEC！")
            return

        # 2. 弹出原生列表让用户选择
        labels = [f"{i + 1}. {r['name']}" for i, r in enumerate(self.REMOTES)]
        idx = dialog_select("请选择需要适配的遥控器", labels)

        if idx < 0:
            return  # 用户按了返回键取消

        selected = self.REMOTES[idx]

        # 3. 动态寻找该遥控器的说明大图
        from ..common.kodi_ui import get_addon
        addon = get_addon()
        addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))
        remote_dir = os.path.join(addon_path, "resources", "data", "remotes", selected["id"])

        img_path = ""
        if os.path.exists(remote_dir):
            # 扫描 .jpg 或 .png
            all_images = [f for f in os.listdir(remote_dir) if f.lower().endswith(('.jpg', '.png'))]
            if all_images:
                # 优先寻找名字里带有 main 或 cover 的图，否则拿第一张
                main_img = next((f for f in all_images if 'main' in f.lower() or 'cover' in f.lower()), None)
                img_path = os.path.join(remote_dir, main_img if main_img else all_images[0])

        # ==========================================
        # 4. 核心视觉交互：全屏大图 + 二次确认弹窗
        # ==========================================
        if img_path:
            # 调用 Kodi 内置命令全屏显示图片
            xbmc.executebuiltin(f'ShowPicture("{img_path}")')
            # 暂停 0.6 秒，让大图有时间渲染出来作为背景
            xbmc.sleep(600)

            # 弹出确认框（此时大图会垫在确认框的后面作为背景）
        confirm_msg = f"即将为系统适配：\n[COLOR yellow]{selected['name']}[/COLOR]\n\n此操作将自动清理旧的遥控器残留配置。\n是否继续应用此配置？"
        confirmed = dialog_yesno(title, confirm_msg)

        if img_path:
            # 无论用户点了“是”还是“否”，都自动关闭背景的大图浏览器
            xbmc.executebuiltin('Window.Close(slideshow)')

        # 如果用户点了“否”或按了返回键，直接退出
        if not confirmed:
            return

        # 5. 用户确认后，执行底层配置部署
        self._apply_config(title, selected)

    def _apply_config(self, title: str, remote_info: dict) -> None:
        # 动态定位插件内遥控器配置的存放路径
        addon_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        source_dir = os.path.join(addon_dir, "data", "remotes", remote_info["id"])

        if not os.path.exists(source_dir):
            dialog_ok(title, f"找不到配置文件库：\n{source_dir}\n请确认对应文件夹是否存在！")
            return

        keymaps_dir = xbmcvfs.translatePath("special://userdata/keymaps/")
        hwdb_dir = "/storage/.config/hwdb.d"
        flash_dir = "/flash"

        os.makedirs(keymaps_dir, exist_ok=True)
        os.makedirs(hwdb_dir, exist_ok=True)

        failed_ops = []
        need_reboot = False
        flash_mounted_rw = False

        try:
            files = os.listdir(source_dir)
            if not files:
                dialog_ok(title, "该遥控器专属目录下没有任何配置文件！")
                return

            # ----------------------------------------------------
            # 步骤 1：深度清理旧配置，防止幽灵按键冲突
            # ----------------------------------------------------
            # 清理旧的 xml 映射（强制删除冲突的 gen.xml，解决 Keymap Editor 报错问题）
            for old_xml in ["gen.xml", "keyboard.xml"]:
                p = os.path.join(keymaps_dir, old_xml)
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception as e:
                        debug(f"Remove old {old_xml} failed: {e}")

            # 清理我们新版脚本生成的独立 xml 文件
            if os.path.exists(keymaps_dir):
                for f in os.listdir(keymaps_dir):
                    if f.startswith("remote_adapter_") and f.endswith(".xml"):
                        try:
                            os.remove(os.path.join(keymaps_dir, f))
                        except Exception:
                            pass

            # 清理旧的 hwdb 映射
            if os.path.exists(hwdb_dir):
                for f in os.listdir(hwdb_dir):
                    if f.endswith(".hwdb"):
                        try:
                            os.remove(os.path.join(hwdb_dir, f))
                            need_reboot = True
                        except Exception as e:
                            debug(f"Remove old hwdb {f} failed: {e}")

            # 清理旧的 /flash/remote.conf (如果新遥控器不需要 conf)
            has_new_conf = any(f.endswith(".conf") for f in files)
            old_conf_path = os.path.join(flash_dir, "remote.conf")
            if not has_new_conf and os.path.exists(old_conf_path):
                run_command(f"mount -o remount,rw {flash_dir}")
                flash_mounted_rw = True
                try:
                    os.remove(old_conf_path)
                    need_reboot = True
                except Exception as e:
                    failed_ops.append("清理旧的 remote.conf 失败")

            # ----------------------------------------------------
            # 步骤 2：智能分发复制新文件
            # ----------------------------------------------------
            for filename in files:
                src_file = os.path.join(source_dir, filename)

                # A. 键位映射文件 -> keymaps
                if filename.endswith(".xml"):
                    # 【核心修复】自动重命名，避开与 Keymap Editor 的 gen.xml 命名冲突
                    safe_name = f"remote_adapter_{filename}" if filename in ["gen.xml",
                                                                             "keyboard.xml"] else filename
                    dst_file = os.path.join(keymaps_dir, safe_name)
                    if not xbmcvfs.copy(src_file, dst_file):
                        failed_ops.append(f"写入失败: {filename}")

                # B. 硬件拦截文件 -> hwdb.d
                elif filename.endswith(".hwdb"):
                    dst_file = os.path.join(hwdb_dir, filename)
                    if xbmcvfs.copy(src_file, dst_file):
                        need_reboot = True
                    else:
                        failed_ops.append(f"写入失败: {filename}")

                # C. 底层红外码配置 -> /flash
                elif filename.endswith(".conf"):
                    if not flash_mounted_rw:
                        run_command(f"mount -o remount,rw {flash_dir}")
                        flash_mounted_rw = True

                    dst_file = os.path.join(flash_dir, filename)
                    if xbmcvfs.copy(src_file, dst_file):
                        run_command("sync")
                        need_reboot = True
                    else:
                        failed_ops.append(f"写入到 /flash 失败: {filename}")

        except Exception as e:
            error(f"Remote adapter failed: {e}\n{traceback.format_exc()}")
            dialog_ok(title, f"适配执行发生异常:\n{str(e)}")
            return
        finally:
            # ----------------------------------------------------
            # 步骤 3：锁回 /flash 保持只读状态
            # ----------------------------------------------------
            if flash_mounted_rw:
                run_command(f"mount -o remount,ro {flash_dir}")

        # ----------------------------------------------------
        # 步骤 4：反馈结果
        # ----------------------------------------------------
        if failed_ops:
            dialog_ok(title, "以下操作执行失败：\n" + "\n".join(failed_ops))
        else:
            if not need_reboot:
                xbmc.executebuiltin("action(reloadkeymaps)")
                dialog_ok(title, f"[COLOR green]【{remote_info['name']}】[/COLOR]\n配置已成功应用并实时生效！")
            else:
                if dialog_yesno(
                    title,
                    f"【{remote_info['name']}】底层映射已写入完成！\n\n[COLOR red]检测到底层硬件驱动文件变更，必须重启才能生效！[/COLOR]\n\n是否立即重启设备？"
                ):
                    xbmc.executebuiltin("Reboot")