#!/usr/bin/env python3
"""
关节方向诊断工具
用于检查录制数据回放时的关节方向问题

Author: VIST Project
Date: 2026-02-22
"""

import os
import sys
import json
import numpy as np
from pathlib import Path

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config


def check_joint_directions():
    """检查关节方向配置"""
    print("=" * 80)
    print("🔍 关节方向诊断工具")
    print("=" * 80)

    # 加载配置
    config = get_config()

    print("\n📋 当前关节方向配置:")
    print("-" * 80)
    joint_names = [
        "Joint 0: Shoulder_Pitch",
        "Joint 1: Shoulder_Roll",
        "Joint 2: Shoulder_Yaw",
        "Joint 3: Elbow_Pitch",
        "Joint 4: Wrist_Yaw",
        "Joint 5: Wrist_Pitch",
        "Joint 6: Wrist_Roll"
    ]

    if hasattr(config, 'robot_joint_directions'):
        for i, (name, direction) in enumerate(zip(joint_names, config.robot_joint_directions)):
            direction_str = "正向 ✅" if direction == 1 else "反向 ⚠️"
            print(f"  {name}: {int(direction):+2d} ({direction_str})")
    else:
        print("  ⚠️  未找到 joint_directions 配置")

    print("\n" + "=" * 80)
    print("📊 数据流分析")
    print("=" * 80)

    print("\n数据流路径:")
    print("  1. 视觉节点 → 人体关键点 (shoulder, elbow, wrist)")
    print("  2. 录制工具 → 保存关键点数据")
    print("  3. 回放工具 → 发送关键点数据")
    print("  4. 控制器 → motion_mapper → IK 求解器 → 关节角度")
    print("  5. 应用关节方向 → q_final = q * joint_directions[i]")

    print("\n" + "=" * 80)
    print("🔧 可能的问题")
    print("=" * 80)

    print("\n1. 仿真和真机使用了不同的配置文件")
    print("   解决方案: 确保使用相同的 system_config.yaml")

    print("\n2. 关节方向配置未正确应用")
    print("   检查位置:")
    print("   - src/core/geometric_arm_solver.py")
    print("   - src/robot/arm_driver.py")
    print("   - scripts/simulate_full_flow.py")

    print("\n3. 录制数据时和回放时使用了不同的坐标系")
    print("   解决方案: 检查 motion_mapper 的坐标转换")

    print("\n" + "=" * 80)
    print("🧪 测试建议")
    print("=" * 80)

    print("\n1. 对比测试:")
    print("   # 直接控制（不录制）")
    print("   python scripts/simulate_full_flow.py")
    print()
    print("   # 录制后回放")
    print("   python scripts/record_vision_data.py data/test.jsonl --duration 10")
    print("   python scripts/simulate_full_flow.py &")
    print("   python scripts/playback_vision_data.py data/test.jsonl")

    print("\n2. 检查关节角度:")
    print("   在仿真环境中添加日志，打印每个关节的角度")
    print("   对比直接控制和回放时的关节角度是否一致")

    print("\n3. 单关节测试:")
    print("   锁定其他关节，只测试一个关节")
    print("   确定是哪个关节方向反了")

    print("\n" + "=" * 80)


def analyze_recording(recording_file):
    """分析录制文件"""
    print("\n" + "=" * 80)
    print(f"📂 分析录制文件: {recording_file}")
    print("=" * 80)

    if not Path(recording_file).exists():
        print(f"❌ 文件不存在: {recording_file}")
        return

    # 读取数据
    with open(recording_file, 'r') as f:
        lines = f.readlines()

    print(f"\n总帧数: {len(lines)}")

    # 分析第一帧
    first_frame = json.loads(lines[0])
    print(f"\n第一帧数据结构:")
    print(json.dumps(first_frame, indent=2)[:500])

    # 检查关键点
    if 'data' in first_frame and 'keypoints' in first_frame['data']:
        keypoints = first_frame['data']['keypoints']
        print(f"\n关键点:")
        for key, value in keypoints.items():
            print(f"  {key}: {value}")

    # 分析运动范围
    print(f"\n分析运动范围...")
    wrist_positions = []
    for line in lines:
        frame = json.loads(line)
        if 'data' in frame and 'keypoints' in frame['data']:
            keypoints = frame['data']['keypoints']
            if 'wrist' in keypoints:
                wrist_positions.append(keypoints['wrist'])

    if wrist_positions:
        wrist_positions = np.array(wrist_positions)
        print(f"  手腕位置范围:")
        print(f"    X: [{wrist_positions[:, 0].min():.3f}, {wrist_positions[:, 0].max():.3f}]")
        print(f"    Y: [{wrist_positions[:, 1].min():.3f}, {wrist_positions[:, 1].max():.3f}]")
        print(f"    Z: [{wrist_positions[:, 2].min():.3f}, {wrist_positions[:, 2].max():.3f}]")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="关节方向诊断工具")
    parser.add_argument("--recording", type=str, default=None,
                        help="录制文件路径（可选）")

    args = parser.parse_args()

    # 检查关节方向配置
    check_joint_directions()

    # 分析录制文件
    if args.recording:
        analyze_recording(args.recording)
    else:
        # 查找最新的录制文件
        recordings_dir = Path("data/recordings")
        if recordings_dir.exists():
            recordings = list(recordings_dir.glob("*.jsonl"))
            if recordings:
                latest = max(recordings, key=lambda p: p.stat().st_mtime)
                print(f"\n💡 提示: 找到最新录制文件 {latest}")
                print(f"   运行: python scripts/diagnose_joint_directions.py --recording {latest}")


if __name__ == "__main__":
    main()