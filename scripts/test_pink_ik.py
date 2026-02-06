#!/usr/bin/env python3
"""
测试 Pink IK 求解器的分层优化功能

测试场景：
1. 手腕位姿优化（6-DoF）
2. 手腕 + 肘部位置优化（分层任务）
"""

import numpy as np
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core.pink_ik_solver import PinkIKSolver

print("=" * 80)
print("🧪 测试 Pink IK 求解器")
print("=" * 80)

# 初始化求解器
solver = PinkIKSolver()

# 测试参数
shoulder_pos = np.array([0.0, -0.096, 1.217])  # 肩部位置
arm_length_total = 0.2908 + 0.2366  # 上臂 + 前臂 = 0.5274m

print("\n" + "=" * 80)
print("测试 1: 手腕位姿优化（仅手腕，无肘部约束）")
print("=" * 80)

# 目标：手腕在肩部正下方（自然下垂）
wrist_target = shoulder_pos + np.array([0.0, 0.0, -arm_length_total])
wrist_quat = np.array([0, 0, 0, 1])  # 无旋转

print(f"\n目标手腕位置: {wrist_target}")
print(f"目标手腕姿态: {wrist_quat}")

q_sol, success, error = solver.solve(
    wrist_target,
    target_quat=wrist_quat,
    elbow_pos=None,  # 不约束肘部
    max_iter=50
)

print(f"\n结果:")
print(f"  成功: {success}")
print(f"  误差: {error*1000:.2f}mm")
print(f"  关节角度: {q_sol}")

print("\n" + "=" * 80)
print("测试 2: 分层优化（手腕 + 肘部位置）")
print("=" * 80)

# 目标：手腕向前伸展 10cm，肘部在特定位置
wrist_target = shoulder_pos + np.array([0.1, 0.0, -arm_length_total * 0.8])
elbow_target = shoulder_pos + np.array([0.05, 0.0, -0.2])  # 肘部在中间位置

print(f"\n目标手腕位置: {wrist_target}")
print(f"目标肘部位置: {elbow_target}")

q_sol, success, error = solver.solve(
    wrist_target,
    target_quat=wrist_quat,
    elbow_pos=elbow_target,  # 约束肘部位置
    q_init=q_sol,  # 使用上次结果作为初始猜测
    max_iter=50
)

print(f"\n结果:")
print(f"  成功: {success}")
print(f"  误差: {error*1000:.2f}mm")
print(f"  关节角度: {q_sol}")

print("\n" + "=" * 80)
print("测试 3: 小幅度运动（模拟遥操作）")
print("=" * 80)

# 从自然下垂开始
wrist_start = shoulder_pos + np.array([0.0, 0.0, -arm_length_total])

# 测试一系列小幅度运动
movements = [
    ("向前 5cm", np.array([0.05, 0.0, 0.0])),
    ("向右 5cm", np.array([0.0, -0.05, 0.0])),
    ("向上 5cm", np.array([0.0, 0.0, 0.05])),
]

q_current = None
for name, delta in movements:
    wrist_target = wrist_start + delta
    print(f"\n{name}: 目标 = {wrist_target}")

    q_sol, success, error = solver.solve(
        wrist_target,
        target_quat=wrist_quat,
        q_init=q_current,
        max_iter=30
    )

    print(f"  成功: {success}, 误差: {error*1000:.2f}mm")
    q_current = q_sol

print("\n" + "=" * 80)
print("✅ 测试完成")
print("=" * 80)
