#!/usr/bin/env python3
"""
简单测试脚本 - 验证 LinkerHandRetargeter 是否能正确处理关键点
"""

import sys
import os
import numpy as np

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.core.linker_hand_retargeter import LinkerHandRetargeter

def test_retargeter():
    """测试 LinkerHandRetargeter 的基本功能"""

    print("=" * 60)
    print("测试 LinkerHandRetargeter")
    print("=" * 60)

    # 1. 初始化
    config_path = os.path.join(PROJECT_ROOT, "config/hand_retargeting_config.yaml")
    retargeter = LinkerHandRetargeter(config_path, PROJECT_ROOT)

    print("\n✅ 初始化成功！")

    # 2. 创建模拟的 MediaPipe 关键点
    keypoints = np.zeros((21, 3))

    # 手腕
    keypoints[0] = [0.0, 0.0, 0.0]

    # 拇指
    keypoints[1] = [0.05, -0.02, 0.0]
    keypoints[2] = [0.08, -0.04, 0.0]
    keypoints[3] = [0.10, -0.06, 0.0]
    keypoints[4] = [0.12, -0.08, 0.0]

    # 食指
    keypoints[5] = [0.03, 0.02, 0.0]
    keypoints[6] = [0.05, 0.05, 0.0]
    keypoints[7] = [0.06, 0.08, 0.0]
    keypoints[8] = [0.07, 0.11, 0.0]

    # 中指
    keypoints[9] = [0.01, 0.03, 0.0]
    keypoints[10] = [0.01, 0.07, 0.0]
    keypoints[11] = [0.01, 0.11, 0.0]
    keypoints[12] = [0.01, 0.14, 0.0]

    # 无名指
    keypoints[13] = [-0.01, 0.02, 0.0]
    keypoints[14] = [-0.02, 0.06, 0.0]
    keypoints[15] = [-0.03, 0.10, 0.0]
    keypoints[16] = [-0.04, 0.13, 0.0]

    # 小指
    keypoints[17] = [-0.03, 0.01, 0.0]
    keypoints[18] = [-0.05, 0.04, 0.0]
    keypoints[19] = [-0.06, 0.07, 0.0]
    keypoints[20] = [-0.07, 0.10, 0.0]

    print("\n📊 输入关键点形状:", keypoints.shape)

    # 3. 处理关键点
    try:
        active_qpos = retargeter.process(keypoints)
        print("\n✅ 处理成功！")
        print(f"📊 输出关节角度形状: {active_qpos.shape}")
        print(f"📊 输出关节角度: {active_qpos}")

        # 4. 验证输出
        assert active_qpos.shape == (10,), f"期望输出形状为 (10,)，实际为 {active_qpos.shape}"
        assert not np.any(np.isnan(active_qpos)), "输出包含 NaN 值"
        assert not np.any(np.isinf(active_qpos)), "输出包含 Inf 值"

        print("\n✅ 所有验证通过！")

        # 5. 显示关节名称和角度
        print("\n📋 关节角度详情：")
        for i, (name, angle) in enumerate(zip(retargeter.ACTIVE_JOINT_NAMES, active_qpos)):
            print(f"   [{i}] {name:20s}: {angle:8.4f} rad ({np.degrees(angle):7.2f}°)")

        return True

    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_retargeter()

    print("\n" + "=" * 60)
    if success:
        print("✅ 测试通过！LinkerHandRetargeter 工作正常。")
    else:
        print("❌ 测试失败！")
    print("=" * 60)

    sys.exit(0 if success else 1)
