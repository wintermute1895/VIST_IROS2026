#!/usr/bin/env python3
"""
测试手臂控制节点的可视化功能
运行此脚本将启动 MeshCat 可视化器并显示简单的正弦波运动
"""
import sys
sys.path.insert(0, '.')

from src.nodes.arm_node import ArmNode

if __name__ == "__main__":
    print("=" * 60)
    print("VIST 手臂控制节点 - 可视化测试")
    print("=" * 60)
    print()
    print("说明:")
    print("1. 此脚本将启动 MeshCat 可视化服务器")
    print("2. 浏览器会自动打开显示机器人模型")
    print("3. 左臂将执行简单的正弦波运动")
    print("4. 按 Ctrl+C 停止")
    print()
    print("=" * 60)
    print()

    # 创建并运行手臂控制节点
    node = ArmNode(visualize=True, dof=7)
    node.run(frequency=50)  # 50 Hz 控制频率
