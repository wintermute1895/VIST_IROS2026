#!/usr/bin/env python3
"""
ROS2 节点状态检查工具
快速检查 VIST 遥操作系统的所有关键节点是否在运行
"""

import subprocess
import sys

# 颜色定义
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def get_running_nodes():
    """获取当前运行的所有 ROS2 节点"""
    try:
        result = subprocess.run(
            ['ros2', 'node', 'list'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip().split('\n')
    except Exception as e:
        print(f"{RED}错误: 无法获取节点列表: {e}{NC}")
        return []

def check_node(node_name, running_nodes):
    """检查单个节点是否在运行"""
    is_running = node_name in running_nodes
    status = f"{GREEN}✓ 运行中{NC}" if is_running else f"{RED}✗ 未运行{NC}"
    print(f"  {node_name:<35} {status}")
    return is_running

def main():
    print(f"{BLUE}========================================{NC}")
    print(f"{BLUE}VIST 系统节点状态检查{NC}")
    print(f"{BLUE}========================================{NC}")
    print()

    # 获取运行中的节点
    running_nodes = get_running_nodes()

    if not running_nodes or running_nodes == ['']:
        print(f"{RED}错误: 没有检测到任何 ROS2 节点{NC}")
        print("请确保：")
        print("1. ROS2 环境已加载")
        print("2. 至少有一个 ROS2 节点在运行")
        sys.exit(1)

    # 定义需要检查的节点
    required_nodes = {
        '相机模块': [
            '/realsense_camera_node',
        ],
        '外骨骼模块': [
            '/linkerta_node',
        ],
        'VIST 滤波器': [
            '/vist_filter_node',
        ],
        '灵巧手模块': [
            '/linker_hand_advanced_l10',
        ],
        '机械臂驱动': [
            '/robot1/lbot_main_node',
            '/robot1/lbot_left_arm_node',
            '/robot1/lbot_right_arm_node',
        ],
        '遥操作桥接': [
            '/teleop_bridge_node',
        ],
    }

    # 检查每个模块
    all_ok = True
    module_status = {}

    for module_name, nodes in required_nodes.items():
        print(f"{YELLOW}{module_name}:{NC}")
        module_ok = True
        for node in nodes:
            if not check_node(node, running_nodes):
                module_ok = False
                all_ok = False
        module_status[module_name] = module_ok
        print()

    # 显示其他运行中的节点
    known_nodes = set()
    for nodes in required_nodes.values():
        known_nodes.update(nodes)

    other_nodes = [n for n in running_nodes if n and n not in known_nodes]
    if other_nodes:
        print(f"{YELLOW}其他节点:{NC}")
        for node in other_nodes:
            print(f"  {node}")
        print()

    # 总结
    print(f"{BLUE}========================================{NC}")
    if all_ok:
        print(f"{GREEN}✓ 所有关键节点都在运行{NC}")
        print(f"{GREEN}系统已就绪，可以开始数据采集{NC}")
    else:
        print(f"{RED}✗ 部分节点未运行{NC}")
        print()
        print("缺失的模块：")
        for module_name, status in module_status.items():
            if not status:
                print(f"  - {module_name}")
        print()
        print("启动建议：")
        print(f"  {YELLOW}快速启动:{NC} ros2 launch bringup teleop_system.launch.py")
        print(f"  {YELLOW}准备脚本:{NC} ./scripts/prepare_system.sh")
    print(f"{BLUE}========================================{NC}")

    sys.exit(0 if all_ok else 1)

if __name__ == '__main__':
    main()
