#!/usr/bin/env python3
"""
测试配置加载和VIST卡尔曼滤波器初始化
"""

import sys
sys.path.insert(0, '/home/ilex/Dev/VIST/ros2_ws/src')

from config.config_loader import VISTConfig

print("=" * 60)
print("测试1: 加载配置文件")
print("=" * 60)

try:
    config = VISTConfig('/home/ilex/Dev/VIST/config/system_config.yaml')
    print("✅ 配置文件加载成功")
except Exception as e:
    print(f"❌ 配置文件加载失败: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("测试2: 检查新增的VIST参数")
print("=" * 60)

# 检查所有新增参数
test_params = [
    ('vist_filter_system_dt', 'float'),
    ('vist_filter_system_process_noise_epsilon', 'float'),
    ('vist_task_covariance_free_variance_xyz', 'list'),
    ('vist_task_covariance_free_variance_rpy', 'list'),
    ('vist_task_covariance_cons_variance_xyz', 'list'),
    ('vist_task_covariance_cons_variance_rpy', 'list'),
    ('vist_gating_z_activation_threshold', 'float'),
    ('vist_gating_dir_epsilon', 'float'),
    ('vist_velocity_perception_velocity_noise_floor', 'float'),
    ('vist_velocity_perception_max_valid_velocity', 'float'),
    ('vist_observation_human_base_variance', 'float'),
    ('vist_observation_human_lambda', 'float'),
    ('vist_observation_virtual_min_variance', 'float'),
    ('vist_observation_conflict_gain', 'float'),
    ('vist_observation_differential_ik_damping', 'float'),
    ('vist_observation_use_orientation_control', 'bool'),
    ('vist_observation_fusion_method', 'str'),
    ('vist_intent_w_task', 'list'),
    ('vist_intent_alpha_beta', 'float'),
    ('vist_intent_w_geo', 'float'),
    ('vist_intent_w_vel', 'float'),
    ('vist_intent_alpha_alignment_power', 'float'),
    ('vist_intent_intent_smoothing', 'float'),
]

all_passed = True
for param_name, param_type in test_params:
    try:
        value = getattr(config, param_name)
        print(f"✅ {param_name}: {value}")
    except AttributeError as e:
        print(f"❌ {param_name}: 属性不存在")
        all_passed = False
    except Exception as e:
        print(f"❌ {param_name}: {e}")
        all_passed = False

if not all_passed:
    print("\n❌ 部分参数检查失败")
    sys.exit(1)

print("\n" + "=" * 60)
print("测试3: 创建模拟的IK求解器")
print("=" * 60)

# 创建一个模拟的IK求解器
class MockIKSolver:
    def __init__(self):
        import pinocchio as pin
        import numpy as np

        # 加载URDF
        urdf_path = '/home/ilex/Dev/VIST/config/urdf/lkls73_o2_dual_arm_description_fsm.urdf'
        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()

        # 设置末端执行器
        self.ee_frame_id = self.model.getFrameId('Right_Wrist_Roll_Link')

        # 受控关节索引（前7个关节）
        self.controlled_indices = list(range(7))

        print(f"✅ 模拟IK求解器创建成功")
        print(f"   - 关节数: {self.model.nq}")
        print(f"   - 末端执行器: Right_Wrist_Roll_Link (ID: {self.ee_frame_id})")

try:
    ik_solver = MockIKSolver()
except Exception as e:
    print(f"❌ IK求解器创建失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("测试4: 初始化VIST卡尔曼滤波器")
print("=" * 60)

try:
    from core.vist_kalman_filter import VISTKalmanFilter

    vist_filter = VISTKalmanFilter(ik_solver, config)
    print("✅ VIST卡尔曼滤波器初始化成功")
    print(f"   - 关节数: {vist_filter.n_joints}")
    print(f"   - 状态维度: {vist_filter.state_dim}")
    print(f"   - 时间步长: {vist_filter.dt}s")
    print(f"   - Z轴激活阈值: {vist_filter.z_activation_threshold}m")
    print(f"   - 阻尼系数: {vist_filter.differential_ik_damping}")

except Exception as e:
    print(f"❌ VIST卡尔曼滤波器初始化失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ 所有测试通过！")
print("=" * 60)