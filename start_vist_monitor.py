#!/usr/bin/env python3
"""
VIST 监控启动脚本

在新终端中运行 VIST 监控节点
"""

import subprocess
import sys

def main():
    print("=" * 70)
    print("启动 VIST 实时监控")
    print("=" * 70)
    print("\n提示：")
    print("  - 确保 vist_filter_node 正在运行")
    print("  - 监控数据将每秒更新一次")
    print("  - 按 Ctrl+C 退出\n")

    try:
        subprocess.run([
            'ros2', 'run', 'nodes', 'vist_monitor.py'
        ])
    except KeyboardInterrupt:
        print("\n监控已停止")
    except Exception as e:
        print(f"错误: {e}")
        print("\n如果找不到节点，请尝试：")
        print("  cd /home/ilex/Dev/VIST/ros2_ws/src/nodes")
        print("  python3 vist_monitor.py")

if __name__ == '__main__':
    main()
