#!/usr/bin/env python3
"""
测试 filters.py 中的 VISTFilter 类
"""

import sys
import os

# 设置正确的Python路径
ros2_ws_src = '/home/ilex/Dev/VIST/ros2_ws/src'
sys.path.insert(0, ros2_ws_src)
os.chdir(ros2_ws_src)

import numpy as np
import pinocchio as pin
from config.config_loader import VISTConfig
from filters import VISTTeleopFilter

print("=" * 60)
print("VISTTeleopFilter 接口测试")
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

# 3. 创建VISTTeleopFilter
try:
    # 计算初始目标位姿
    q_init = np.zeros(ik_solver.model.nq)
    pin.forwardKinematics(ik_solver.model, ik_solver.data, q_init)
    pin.updateFramePlacements(ik_solver.model, ik_solver.data)
    target_pose = ik_solver.data.oMf[ik_solver.ee_frame_id]

    vist_filter = VISTTeleopFilter(
        ik_solver=ik_solver,
        tcp_compensation=None,
        target_pose=target_pose,
        vist_config=config,
        geometric_solver=None
    )
    print("✅ VISTTeleopFilter 创建成功")
except Exception as e:
    print(f"❌ VISTTeleopFilter 创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. 测试update方法
print("\n" + "=" * 60)
print("测试 update 方法")
print("=" * 60)

q_in = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
dt = 0.02

try:
    for i in range(5):
        q_out = vist_filter.update(q_in, dt)
        print(f"迭代 {i+1}: 输入={q_in[:3]}... 输出={q_out[:3]}...")

    print("\n✅ update 方法测试成功！")
except Exception as e:
    print(f"\n❌ update 方法测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. 测试reset方法
print("\n" + "=" * 60)
print("测试 reset 方法")
print("=" * 60)

try:
    vist_filter.reset()
    print("✅ reset 方法测试成功！")
except Exception as e:
    print(f"❌ reset 方法测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)
