#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XWool Web管理界面启动脚本

该脚本用于启动XWool的Web管理界面，提供友好的用户交互体验。
支持通过命令行输入'q'来优雅地停止服务器。

作者: XWool Team
版本: 1.0.0
"""

import os
import signal
import subprocess
import sys
import threading
import time
from typing import List


# 配置常量
class Config:
    """应用配置常量"""
    FLASK_APP = 'app.py'
    DEFAULT_PORT = 5001
    STARTUP_DELAY = 2
    EXIT_COMMAND = 'q'
    PYTHON_CMD = 'python'


def run_flask() -> None:
    """
    运行Flask应用

    在单独的线程中启动Flask应用，处理启动过程中的异常。

    Raises:
        SystemExit: 当Flask应用启动失败或收到中断信号时退出
    """
    try:
        print("🔄 正在启动Flask应用...")
        subprocess.run([Config.PYTHON_CMD, Config.FLASK_APP], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Flask应用启动失败: {e}")
        print("💡 请检查app.py文件是否存在且可执行")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  服务器已停止")
        sys.exit(0)
    except FileNotFoundError:
        print(f"❌ 找不到文件: {Config.FLASK_APP}")
        print("💡 请确保app.py文件存在于当前目录")
        sys.exit(1)


def find_flask_processes() -> List[str]:
    """
    查找Flask应用进程ID

    Returns:
        List[str]: Flask进程ID列表
    """
    try:
        result = subprocess.run(
            ['pgrep', '-f', f'{Config.PYTHON_CMD}.*{Config.FLASK_APP}'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.stdout:
            return [pid.strip() for pid in result.stdout.strip().split('\n')
                    if pid.strip()]
        return []
    except Exception as e:
        print(f"⚠️  查找进程时出错: {e}")
        return []


def terminate_flask_processes() -> bool:
    """
    终止Flask应用进程

    Returns:
        bool: 是否成功终止进程
    """
    try:
        pids = find_flask_processes()
        if not pids:
            print("ℹ️  未找到运行中的Flask进程")
            return True

        print(f"🔄 正在终止 {len(pids)} 个Flask进程...")
        success_count = 0

        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
                print(f"✅ 已终止进程 {pid}")
                success_count += 1
            except ProcessLookupError:
                print(f"ℹ️  进程 {pid} 已不存在")
            except PermissionError:
                print(f"❌ 无权限终止进程 {pid}")
            except ValueError:
                print(f"❌ 无效的进程ID: {pid}")

        return success_count > 0

    except Exception as e:
        print(f"⚠️  终止进程时出错: {e}")
        return False


def check_exit() -> None:
    """
    检查用户输入，如果输入退出命令则优雅地停止服务器

    监听用户输入，当用户输入'q'时，查找并终止Flask进程。
    """
    print(f"💡 输入 '{Config.EXIT_COMMAND}' 并按回车键来停止服务器")

    while True:
        try:
            user_input = input().strip().lower()
            if user_input == Config.EXIT_COMMAND:
                print("🔄 正在停止服务器...")
                if terminate_flask_processes():
                    print("✅ 服务器已成功停止")
                else:
                    print("⚠️  服务器停止过程中遇到问题")
                sys.exit(0)
            elif user_input in ['help', 'h', '?']:
                print(f"💡 输入 '{Config.EXIT_COMMAND}' 停止服务器")
            elif user_input:
                print(f"❓ 未知命令: {user_input}")
                print(f"💡 输入 '{Config.EXIT_COMMAND}' 停止服务器")

        except (EOFError, KeyboardInterrupt):
            print("\n🔄 收到中断信号，正在停止服务器...")
            terminate_flask_processes()
            sys.exit(0)


def print_banner() -> None:
    """打印启动横幅"""
    print("=" * 60)
    print("🚀 XWool Web管理界面")
    print("=" * 60)
    print(f"📱 访问地址: http://localhost:{Config.DEFAULT_PORT}")
    print("⏹️  按 Ctrl+C 停止服务器")
    print("=" * 60)


def check_dependencies() -> bool:
    """
    检查依赖项是否存在

    Returns:
        bool: 依赖项是否满足
    """
    if not os.path.exists(Config.FLASK_APP):
        print(f"❌ 找不到Flask应用文件: {Config.FLASK_APP}")
        print("💡 请确保app.py文件存在于当前目录")
        return False

    try:
        # 检查Python是否可用
        subprocess.run([Config.PYTHON_CMD, '--version'],
                       capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"❌ Python命令不可用: {Config.PYTHON_CMD}")
        print("💡 请确保Python已正确安装并在PATH中")
        return False

    return True


def main() -> None:
    """
    主函数

    启动XWool Web管理界面的主入口点。
    检查依赖项，启动Flask应用，并监听用户输入。
    """
    print_banner()

    # 检查依赖项
    if not check_dependencies():
        sys.exit(1)

    try:
        # 启动Flask应用
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # 等待Flask启动
        print(f"⏳ 等待Flask应用启动 ({Config.STARTUP_DELAY}秒)...")
        time.sleep(Config.STARTUP_DELAY)

        if flask_thread.is_alive():
            print("✅ Flask应用启动成功")
        else:
            print("❌ Flask应用启动失败")
            sys.exit(1)

        # 检查退出命令
        check_exit()

    except KeyboardInterrupt:
        print("\n🔄 收到中断信号，正在停止服务器...")
        terminate_flask_processes()
        print("✅ 服务器已停止")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 启动过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
