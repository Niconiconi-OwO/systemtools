# -*- coding: utf-8 -*-
"""Tool: CoreELEC Daily Auto Reboot via systemd timers."""

import os
import xbmcgui
import traceback
from typing import Dict

from ..common.kodi_ui import (
    dialog_ok,
    dialog_select,
    get_string,
)
from ..common.logger import error, info
from ..common.system_exec import run_command
from .base_tool import BaseTool, ToolRegistry

SYSTEMD_DIR = "/storage/.config/system.d"
SERVICE_FILE = os.path.join(SYSTEMD_DIR, "daily-reboot.service")
TIMER_FILE = os.path.join(SYSTEMD_DIR, "daily-reboot.timer")


@ToolRegistry.register
class AutoRebootTool(BaseTool):
    id = "auto_reboot"
    title_id = 31500  # 菜单标题的语言包 ID
    description_id = 31501  # 菜单描述的语言包 ID
    icon = "DefaultPower.png"
    order = 35  # 排序权重，放在清理工具附近

    def run(self, params: Dict[str, str]) -> None:
        title = get_string(self.title_id, "每日自动重启")
        info("Auto Reboot Tool invoked")

        # 1. 检查是否为 CoreELEC 环境
        if not os.path.exists("/storage/.config"):
            dialog_ok(title, "此功能底层基于 systemd，仅支持 CoreELEC 系统！")
            return

        # 2. 读取当前定时器状态
        current_time = self._get_current_time()
        status_text = f"[COLOR green]已开启 (每天 {current_time})[/COLOR]" if current_time else "[COLOR gray]未开启[/COLOR]"

        options = [
            "1. 设置 / 修改 自动重启时间",
            "2. 关闭 每日自动重启"
        ]

        idx = dialog_select(f"{title} - 当前状态: {status_text}", options)

        if idx == 0:
            self._set_timer(title, current_time)
        elif idx == 1:
            self._disable_timer(title)

    def _get_current_time(self):
        """解析 timer 文件获取当前设定的时间"""
        if not os.path.exists(TIMER_FILE):
            return None
        try:
            import re
            with open(TIMER_FILE, "r") as f:
                content = f.read()
                # 放宽正则匹配规则，兼容 Kodi 返回的 4:00 或 04:00，以及各种空格格式
                match = re.search(r"OnCalendar=.*?(\d{1,2}:\d{2})", content)
                if match:
                    time_str = match.group(1)
                    # 补齐前导 0，让 4:00 在 UI 上显示为 04:00，更整齐美观
                    if len(time_str) == 4:
                        time_str = "0" + time_str
                    return time_str
        except Exception as e:
            error(f"Failed to read timer file: {e}")
        return None

    def _set_timer(self, title: str, current_time: str):
        # 使用 Kodi 原生的时间拨盘 (numeric type 2 表示时间输入)
        default_time = current_time if current_time else "04:00"
        time_str = xbmcgui.Dialog().numeric(2, "请设置每天自动重启的时间", default_time)

        if not time_str:
            return  # 用户取消操作

        os.makedirs(SYSTEMD_DIR, exist_ok=True)

        # 写入 systemd Service (已移除中文注释，避免 ascii 编码报错)
        service_content = """[Unit]
Description=Daily Auto Reboot Service
After=network-online.target time-sync.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'UPTIME=$(cut -d. -f1 /proc/uptime); if [ "$UPTIME" -gt 600 ]; then /usr/sbin/reboot; else echo "Uptime too short, skipping reboot."; fi'
"""
        # 写入 systemd Timer (定义触发的时间)
        timer_content = f"""[Unit]
Description=Daily Auto Reboot Timer

[Timer]
OnCalendar=*-*-* {time_str}:00
Persistent=false

[Install]
WantedBy=timers.target
"""
        try:
            # 强制指定 encoding="utf-8" 双重保险，彻底杜绝编码报错
            with open(SERVICE_FILE, "w", encoding="utf-8") as f:
                f.write(service_content)
            with open(TIMER_FILE, "w", encoding="utf-8") as f:
                f.write(timer_content)

            # 重新加载 systemd 并启动定时器
            run_command("systemctl daemon-reload")
            run_command("systemctl enable daily-reboot.timer")
            run_command("systemctl restart daily-reboot.timer")

            dialog_ok(title,
                      f"设置成功！\n系统将在每天 [COLOR yellow]{time_str}[/COLOR] 自动执行重启。\n(已开启防死循环保护)")
        except Exception as e:
            error(f"Failed to set auto reboot: {e}\n{traceback.format_exc()}")
            dialog_ok(title, f"设置失败，发生异常:\n{str(e)}")

    def _disable_timer(self, title: str):
        if not os.path.exists(TIMER_FILE):
            dialog_ok(title, "当前未开启自动重启，无需关闭。")
            return

        try:
            # 停止并禁用定时器
            run_command("systemctl stop daily-reboot.timer")
            run_command("systemctl disable daily-reboot.timer")

            # 删除配置文件
            if os.path.exists(SERVICE_FILE):
                os.remove(SERVICE_FILE)
            if os.path.exists(TIMER_FILE):
                os.remove(TIMER_FILE)

            # 刷新 systemd 状态
            run_command("systemctl daemon-reload")
            dialog_ok(title, "已成功关闭每日自动重启功能。")
        except Exception as e:
            error(f"Failed to disable auto reboot: {e}\n{traceback.format_exc()}")
            dialog_ok(title, f"关闭失败，发生异常:\n{str(e)}")