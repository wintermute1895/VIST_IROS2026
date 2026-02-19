#!/usr/bin/env python3
"""
测试参数覆盖功能

验证：
1. 配置正确加载
2. 参数覆盖文件正确读取
3. detect_intent使用覆盖的α值
"""

import sys
import os
from pathlib import Path
import numpy as np

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_config
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.utils.parameter_override import ParameterOverrideManager

def test_parameter_override():
    """测试参数覆盖功能"""

    print("=" * 80)
    print("🧪 测试参数覆盖功能")
    print("=" * 80)

    # 1. 加载配置
    print("\n[1/5] 加载配置...")
    config = get_config()
    print(f"✅ ik_strategy: {config.ik_strategy}")
    print(f"✅ vist_simulation_use_parameter_override: {config.vist_simulation_use_parameter_override}")

    # 2. 检查参数覆盖文件
    print("\n[2/5] 检查参数覆盖文件...")
    override_manager = ParameterOverrideManager()
    override = override_manager.get_override()
    print(f"✅ alpha_override: {override.alpha_override}")
    print(f"✅ manifold_enabled_override: {override.manifold_enabled_override}")

    # 3. 初始化IK求解器
    print("\n[3/5] 初始化IK求解器...")
    urdf_path = project_root / "config" / "lkls73_o2_dual_arm_description.urdf"
    ik_solver = PinocchioIKSolver(
        urdf_path=str(urdf_path),
        end_effector_frame="Right_Wrist_Roll_Link"
    )
    print("✅ IK求解器初始化完成")

    # 4. 初始化VIST卡尔曼滤波器
    print("\n[4/5] 初始化VIST卡尔曼滤波器...")
    vist_filter = VISTKalmanFilter(ik_solver, config)
    print("✅ VIST滤波器初始化完成")

    # 5. 测试detect_intent
    print("\n[5/5] 测试detect_intent...")
    target_pos = np.array([0.3, -0.2, 1.0])
    current_pos = np.array([0.3, -0.2, 1.05])
    velocity = np.array([0.0, 0.0, -0.01])

    alpha = vist_filter.detect_intent(target_pos, current_pos, velocity)

    print(f"✅ detect_intent返回的α: {alpha:.4f}")
    print(f"✅ vist_filter.alpha: {vist_filter.alpha:.4f}")
    print(f"✅ vist_filter.alpha_smoothed: {vist_filter.alpha_smoothed:.4f}")

    # 验证
    print("\n" + "=" * 80)
    print("📊 验证结果")
    print("=" * 80)

    if override.alpha_override is not None:
        expected_alpha = override.alpha_override
        # 第一次调用，平滑后的值应该接近覆盖值（但不完全相等，因为有EMA平滑）
        # alpha_smoothed = 0.9 * 0.0 + 0.1 * 1.0 = 0.1
        expected_smoothed = (1.0 - config.vist_intent_smoothing) * expected_alpha

        print(f"期望α (覆盖值): {expected_alpha}")
        print(f"期望α_smoothed (首次): {expected_smoothed:.4f}")
        print(f"实际α: {vist_filter.alpha:.4f}")
        print(f"实际α_smoothed: {vist_filter.alpha_smoothed:.4f}")

        if abs(vist_filter.alpha - expected_alpha) < 0.01:
            print("\n✅ 参数覆盖功能正常工作！")
            print("   α值使用了覆盖文件中的值，而不是从视觉数据计算")
            return True
        else:
            print("\n❌ 参数覆盖功能未生效！")
            print("   α值没有使用覆盖文件中的值")
            return False
    else:
        print("⚠️ 覆盖文件中没有设置alpha_override")
        return False

if __name__ == "__main__":
    success = test_parameter_override()
    sys.exit(0 if success else 1)