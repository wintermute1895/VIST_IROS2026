#!/usr/bin/env python3
"""
视觉-控制接口单元测试

测试内容：
1. VisionPacket 数据契约
2. VisionSafetyLayer 安全检查
3. MockVisionSystem 模拟系统
4. VisionControlBridge 桥接器
"""

import sys
import os
import time
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.interfaces.vision_packet import (
    VisionPacket, Keypoint3D, TrackingStatus,
    create_vision_packet_from_dict
)
from src.interfaces.vision_system import MockVisionSystem
from src.interfaces.vision_safety import VisionSafetyLayer, SafetyAction


def test_vision_packet():
    """测试 VisionPacket 数据契约"""
    print("\n" + "="*60)
    print("测试 1: VisionPacket 数据契约")
    print("="*60)

    # 创建测试数据
    keypoints = {
        'shoulder': np.array([0.0, 0.0, 0.0]),
        'elbow': np.array([0.0, 0.2, 0.3]),
        'wrist': np.array([0.0, 0.2, 0.6]),
        'index_mcp': np.array([0.0, 0.25, 0.65]),
        'pinky_mcp': np.array([0.0, 0.15, 0.65])
    }

    confidences = {
        'shoulder': 1.0,
        'elbow': 0.95,
        'wrist': 0.98,
        'index_mcp': 0.90,
        'pinky_mcp': 0.90
    }

    # 创建数据包
    packet = create_vision_packet_from_dict(
        keypoints,
        confidences,
        tracking_status=TrackingStatus.TRACKING,
        source_algorithm="TestAlgorithm",
        frame_id=1
    )

    # 验证数据
    print(f"✅ 数据包创建成功")
    print(f"   {packet.get_summary()}")

    # 测试方法
    assert packet.is_tracking_valid(), "追踪状态应该有效"
    assert packet.get_all_keypoints_valid(min_confidence=0.8), "所有关键点应该有效"
    assert not packet.is_stale(max_age=1.0), "数据不应该陈旧"

    # 测试格式转换
    human_kps = packet.to_motion_mapper_format()
    assert 'shoulder' in human_kps, "应该包含 shoulder"
    assert 'wrist' in human_kps, "应该包含 wrist"

    print("✅ 所有 VisionPacket 测试通过")


def test_safety_layer():
    """测试 VisionSafetyLayer 安全检查"""
    print("\n" + "="*60)
    print("测试 2: VisionSafetyLayer 安全检查")
    print("="*60)

    safety = VisionSafetyLayer()

    # 测试 1: 正常数据
    print("\n[测试 2.1] 正常数据")
    keypoints = {
        'shoulder': np.array([0.0, 0.0, 0.0]),
        'elbow': np.array([0.0, 0.2, 0.3]),
        'wrist': np.array([0.0, 0.2, 0.6]),
        'index_mcp': np.array([0.0, 0.25, 0.65]),
        'pinky_mcp': np.array([0.0, 0.15, 0.65])
    }
    packet = create_vision_packet_from_dict(keypoints, frame_id=1)
    result = safety.check(packet)
    assert result.is_safe(), "正常数据应该通过检查"
    print(f"   ✅ {result}")

    # 测试 2: 陈旧数据
    print("\n[测试 2.2] 陈旧数据")
    old_packet = create_vision_packet_from_dict(keypoints, frame_id=2)
    old_packet.timestamp = time.time() - 1.0  # 1秒前
    result = safety.check(old_packet)
    assert not result.is_safe(), "陈旧数据应该被拒绝"
    print(f"   ✅ {result}")

    # 测试 3: 目标跳变
    print("\n[测试 2.3] 目标跳变")
    # 先发送正常数据
    packet1 = create_vision_packet_from_dict(keypoints, frame_id=3)
    safety.check(packet1)
    time.sleep(0.01)

    # 然后发送跳变数据
    jump_keypoints = keypoints.copy()
    jump_keypoints['wrist'] = np.array([0.0, 0.5, 0.6])  # 跳变30cm
    packet2 = create_vision_packet_from_dict(jump_keypoints, frame_id=4)
    result = safety.check(packet2)
    assert result.should_stop(), "大幅跳变应该触发急停"
    print(f"   ✅ {result}")

    # 测试 4: 低置信度
    print("\n[测试 2.4] 低置信度")
    low_conf = {'wrist': 0.2, 'elbow': 0.2, 'shoulder': 0.2,
                'index_mcp': 0.2, 'pinky_mcp': 0.2}
    packet3 = create_vision_packet_from_dict(keypoints, low_conf, frame_id=5)
    result = safety.check(packet3)
    assert not result.is_safe(), "低置信度应该被拒绝"
    print(f"   ✅ {result}")

    # 测试 5: 遮挡
    print("\n[测试 2.5] 遮挡")
    packet4 = create_vision_packet_from_dict(
        keypoints,
        tracking_status=TrackingStatus.OCCLUDED,
        frame_id=6
    )
    result = safety.check(packet4)
    print(f"   ✅ {result}")

    # 打印统计
    safety.print_statistics()

    print("✅ 所有 SafetyLayer 测试通过")


def test_mock_vision_system():
    """测试 MockVisionSystem 模拟系统"""
    print("\n" + "="*60)
    print("测试 3: MockVisionSystem 模拟系统")
    print("="*60)

    vision = MockVisionSystem()

    # 初始化
    assert vision.initialize(), "初始化应该成功"
    print("✅ 初始化成功")

    # 启动
    assert vision.start(), "启动应该成功"
    print("✅ 启动成功")

    # 获取数据
    for i in range(5):
        packet = vision.get_latest_frame(timeout=0.1)
        assert packet is not None, "应该返回数据包"
        print(f"   帧 {i+1}: {packet.get_summary()}")
        time.sleep(0.033)

    # 停止
    assert vision.stop(), "停止应该成功"
    print("✅ 停止成功")

    # 清理
    vision.cleanup()
    print("✅ 清理成功")

    print("✅ 所有 MockVisionSystem 测试通过")


def test_integration():
    """测试完整集成"""
    print("\n" + "="*60)
    print("测试 4: 完整集成测试")
    print("="*60)

    # 初始化组件
    vision = MockVisionSystem()
    safety = VisionSafetyLayer()

    vision.initialize()
    vision.start()

    # 运行10帧
    passed = 0
    rejected = 0

    for i in range(10):
        # 获取数据
        packet = vision.get_latest_frame(timeout=0.1)

        # 安全检查
        result = safety.check(packet)

        if result.is_safe():
            passed += 1
            # 转换为 motion_mapper 格式
            human_kps = packet.to_motion_mapper_format()
            print(f"   帧 {i+1}: ✅ 通过 - wrist={human_kps['wrist']}")
        else:
            rejected += 1
            print(f"   帧 {i+1}: ❌ 拒绝 - {result.reason}")

        time.sleep(0.033)

    vision.stop()
    vision.cleanup()

    print(f"\n统计: 通过={passed}, 拒绝={rejected}")
    assert passed > 0, "应该有通过的帧"

    print("✅ 完整集成测试通过")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("🧪 视觉-控制接口单元测试")
    print("="*60)

    try:
        test_vision_packet()
        test_safety_layer()
        test_mock_vision_system()
        test_integration()

        print("\n" + "="*60)
        print("✅ 所有测试通过！")
        print("="*60)

    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1

    except Exception as e:
        print(f"\n❌ 测试错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
