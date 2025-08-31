#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import threading
import time

def run_flask():
    """运行Flask应用"""
    try:
        subprocess.run(['python', 'app.py'], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Flask应用启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⏹️  服务器已停止")
        sys.exit(0)

def check_exit():
    """检查用户输入，如果输入q则退出"""
    while True:
        try:
            user_input = input().strip().lower()
            if user_input == 'q':
                print("🔄 正在停止服务器...")
                # 发送SIGTERM信号给Flask进程
                import os
                import signal
                try:
                    # 查找Flask进程并终止
                    result = subprocess.run(['pgrep', '-f', 'python.*app.py'], 
                                          capture_output=True, text=True)
                    if result.stdout:
                        pids = result.stdout.strip().split('\n')
                        for pid in pids:
                            if pid:
                                os.kill(int(pid), signal.SIGTERM)
                                print(f"✅ 已终止进程 {pid}")
                except Exception as e:
                    print(f"⚠️  终止进程时出错: {e}")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)

def main():
    print("🚀 启动XWool Web管理界面...")
    print("📱 访问地址: http://localhost:5001")
    print("⏹️  按 Ctrl+C 停止服务器")
    print("")
    print("或者 输入 q 回车，退出")
    print("")
    
    # 启动Flask应用
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # 等待Flask启动
    time.sleep(2)
    
    # 检查退出命令
    check_exit()

if __name__ == "__main__":
    main() 