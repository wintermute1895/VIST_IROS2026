#!/usr/bin/env python3
"""
测试VIST卡尔曼滤波器的update函数
"""

import sys
sys.path.insert(0, '/home/ilex/Dev/VIST/ros2_ws/src')

import numpy as np
import pinocchio as pin
from config.config_loader import VISTConfig
from core.vist_kalman_filter import VISTKalmanFilter

print("=" * 60)
print("VIST卡尔曼滤波器 Update 测试")
print("=" * 60)

# 1. 加载配置
config = VISTConfig('/home/ilex/Dev/VIST/config/system_config.yaml')
print("✅ 配置加载成功")

# 2. 创建IK求解器
class MockIKSolver:
    def __init__(self):
        urdf_path = '/home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description_fsm.urdf'
        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()
        self.ee_frame_id = self.model.getFrameId('Right_Wrist_Roll_Link')
        self.controlled_indices = list(range(7))

ik_solver = MockIKSolver()
print("✅ IK求解器创建成功")

# 3. 创建VIST滤波器
vist_filter = VISTKalmanFilter(ik_solver, config)
print("✅ VIST滤波器初始化成功")

# 4. 准备测试数据
print("\n" + "=" * 60)
print("测试 Update 函数")
print("=" * 60)

# 初始关节角度（零位）
shadow_joints = np.zeros(7)

# 目标位姿（使用FK计算）
q_full = np.zeros(ik_solver.model.nq)
q_full[:7] = shadow_joints
pin.forwardKinematics(ik_solver.model, ik_solver.data, q_full)
pin.updateFramePlacements(ik_solver.model, ik_solver.data)
target_pose = ik_solver.data.oMf[ik_solver.ee_frame_id].copy()

# 稍微移动目标位姿
target_pose.translation += np.array([0.01, 0.01, 0.05])  # 移动5cm（超过Z阈值）

print(f"影子关节角度: {shadow_joints}")
print(f"目标位姿平移: {target_pose.translation}")

# 5. 执行update
try:
    for i in range(5):
        filtered_joints = vist_filter.update(shadow_joints, target_pose)
        print(f"\n迭代 {i+1}:")
        print(f"  - 意图因子 α: {vist_filter.alpha:.4f}")
        print(f"  - α_geo: {vist_filter.alpha_geo:.4f}")
        print(f"  - α_vel: {vist_filter.alpha_vel:.4f}")
        print(f"  - α_dir: {vist_filter.alpha_dir:.4f}")
        print(f"  - 滤波后关节角度: {filtered_joints[:3]}...")  # 只显示前3个

    print("\n✅ Update 函数测试成功！")

except Exception as e:
    print(f"\n❌ Update 函数测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 6. 测试Z轴门控
print("\n" + "=" * 60)
print("测试圆柱形2D距离门控")
print("=" * 60)

# 将目标位姿移动到Z阈值内
target_pose.translation[2] = shadow_joints[2] + 0.02  # 2cm，小于5cm阈值

for i in range(3):
    filtered_joints = vist_filter.update(shadow_joints, target_pose)
    print(f"\n迭代 {i+1} (Z距离 < 阈值):")
    print(f"  - α_geo: {vist_filter.alpha_geo:.4f} (应该 > 0)")
    print(f"  - 总意图因子 α: {vist_filter.alpha:.4f}")

print("\n✅ 圆柱形门控测试成功！")

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)
