#!/usr/bin/env python3
"""
视觉-控制接口集成示例

展示如何使用标准接口将视觉模块与控制模块集成。

架构：
┌─────────────────┐
│  Vision System  │ (可替换：MediaPipe, YOLO, etc.)
└────────┬────────┘
         │ VisionPacket
         ▼
┌─────────────────┐
│  Safety Layer   │ (数据验证、异常检测)
└────────┬────────┘
         │ SafetyCheckResult
         ▼
┌─────────────────┐
│ Motion Mapper   │ (人体→机器人映射)
└────────┬────────┘
         │ target_pos, target_quat
         ▼
┌─────────────────┐
│ VIST Filter     │ (卡尔曼滤波 + IK)
└────────┬────────┘
         │ joint_angles
         ▼
┌─────────────────┐
│  Robot Driver   │ (硬件控制)
└─────────────────┘
"""

import sys
import os
import time
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from src.interfaces.vision_system import IVisionSystem, MockVisionSystem
from src.interfaces.vision_safety import VisionSafetyLayer, SafetyAction
from src.interfaces.vision_packet import VisionPacket
from src.core.motion_mapper import ArmMotionMapper
from src.config import get_config


class VisionControlBridge:
    """
    视觉-控制桥接器

    职责：
    1. 管理视觉系统生命周期
    2. 执行安全检查
    3. 数据格式转换
    4. 异常处理和降级
    """

    def __init__(self, vision_system: IVisionSystem, config=None):
        """
        初始化桥接器

        Args:
            vision_system: 视觉系统实例（实现 IVisionSystem 接口）
            config: 配置对象（可选）
        """
        self.vision_system = vision_system
        self.safety_layer = VisionSafetyLayer(config)
        self.config = config or get_config()

        # 统计信息
        self.frame_count = 0
        self.error_count = 0
        self.last_valid_data = None

        print("🌉 [Bridge] 视觉-控制桥接器初始化完成")
        print(f"   视觉算法: {vision_system.get_algorithm_name()}")

    def start(self) -> bool:
        """启动桥接器"""
        print("🌉 [Bridge] 启动桥接器...")

        # 初始化视觉系统
        if not self.vision_system.initialize():
            print("❌ [Bridge] 视觉系统初始化失败")
            return False

        # 启动视觉系统
        if not self.vision_system.start():
            print("❌ [Bridge] 视觉系统启动失败")
            return False

        print("✅ [Bridge] 桥接器启动成功")
        return True

    def stop(self) -> None:
        """停止桥接器"""
        print("🌉 [Bridge] 停止桥接器...")
        self.vision_system.stop()
        self.vision_system.cleanup()
        self.safety_layer.print_statistics()
        print("✅ [Bridge] 桥接器已停止")

    def get_safe_vision_data(self, timeout: float = 0.1) -> tuple:
        """
        获取经过安全检查的视觉数据

        Returns:
            tuple: (packet, check_result)
                - packet: VisionPacket 或 None
                - check_result: SafetyCheckResult
        """
        # 1. 从视觉系统获取数据
        packet = self.vision_system.get_latest_frame(timeout)

        # 2. 安全检查
        check_result = self.safety_layer.check(packet)

        # 3. 统计
        self.frame_count += 1
        if not check_result.is_safe():
            self.error_count += 1

        return packet, check_result

    def get_motion_mapper_input(self, timeout: float = 0.1) -> tuple:
        """
        获取 ArmMotionMapper 所需的输入数据

        Returns:
            tuple: (human_kps, check_result)
                - human_kps: Dict[str, np.ndarray] 或 None
                - check_result: SafetyCheckResult
        """
        packet, check_result = self.get_safe_vision_data(timeout)

        if not check_result.is_safe():
            return None, check_result

        # 转换为 motion_mapper 格式
        human_kps = packet.to_motion_mapper_format()
        self.last_valid_data = human_kps

        return human_kps, check_result

    def get_vist_filter_input(self, timeout: float = 0.1) -> tuple:
        """
        获取 VIST Kalman Filter 所需的输入数据

        Returns:
            tuple: (target_pos, target_quat, elbow_pos, shoulder_pos, check_result)
        """
        packet, check_result = self.get_safe_vision_data(timeout)

        if not check_result.is_safe():
            return None, None, None, None, check_result

        # 提取 VIST 所需的数据
        target_pos = packet.wrist.position
        target_quat = None  # 如果需要姿态，可以从 motion_mapper 计算
        elbow_pos = packet.elbow.position
        shoulder_pos = packet.shoulder.position

        return target_pos, target_quat, elbow_pos, shoulder_pos, check_result


# ==========================================
# 完整集成示例
# ==========================================

def example_full_integration():
    """完整的视觉-控制集成示例"""
    print("\n" + "="*60)
    print("🚀 视觉-控制接口集成示例")
    print("="*60)

    # ==========================================
    # 1. 初始化组件
    # ==========================================
    print("\n📦 步骤 1: 初始化组件")

    # 视觉系统（这里使用模拟系统，实际使用时替换为真实系统）
    vision_system = MockVisionSystem()

    # 桥接器
    bridge = VisionControlBridge(vision_system)

    # 运动映射器
    motion_mapper = ArmMotionMapper()

    # ==========================================
    # 2. 启动系统
    # ==========================================
    print("\n🚀 步骤 2: 启动系统")
    if not bridge.start():
        print("❌ 系统启动失败")
        return

    # ==========================================
    # 3. 主控制循环
    # ==========================================
    print("\n🔄 步骤 3: 主控制循环（运行10帧）")
    print("-"*60)

    try:
        for i in range(10):
            # 3.1 获取视觉数据（经过安全检查）
            human_kps, check_result = bridge.get_motion_mapper_input(timeout=0.1)

            print(f"\n[帧 {i+1}] {check_result}")

            # 3.2 检查安全性
            if check_result.should_stop():
                print("🛑 触发紧急停止！")
                break

            if not check_result.is_safe():
                print("⚠️  数据不安全，跳过此帧")
                continue

            # 3.3 运动映射（人体 → 机器人）
            result = motion_mapper.human_to_robot(human_kps)

            if result is None:
                print("⚠️  运动映射失败（奇异配置）")
                continue

            target_pos, target_quat, debug_info = result

            print(f"   ✅ 目标位置: [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}]")
            print(f"   ✅ 目标姿态: [{target_quat[0]:.2f}, {target_quat[1]:.2f}, "
                  f"{target_quat[2]:.2f}, {target_quat[3]:.2f}]")

            # 3.4 这里可以继续调用 VIST Filter 和 Robot Driver
            # vist_filter.solve(target_pos, target_quat, elbow_pos=..., shoulder_pos=...)
            # robot_driver.move_to(joint_angles)

            time.sleep(0.033)  # 模拟30Hz控制频率

    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")

    finally:
        # ==========================================
        # 4. 清理资源
        # ==========================================
        print("\n🧹 步骤 4: 清理资源")
        bridge.stop()

    print("\n" + "="*60)
    print("✅ 示例完成")
    print("="*60)


# ==========================================
# 示例：如何替换视觉算法
# ==========================================

def example_vision_algorithm_replacement():
    """展示如何无缝替换视觉算法"""
    print("\n" + "="*60)
    print("🔄 视觉算法替换示例")
    print("="*60)

    # 方案 1: 使用 MockVision（测试）
    vision_v1 = MockVisionSystem()
    bridge_v1 = VisionControlBridge(vision_v1)

    # 方案 2: 使用 MediaPipe（实际部署）
    # from src.vision.mediapipe_vision import MediaPipeVision
    # vision_v2 = MediaPipeVision()
    # bridge_v2 = VisionControlBridge(vision_v2)

    # 方案 3: 使用 YOLO + DepthAI（高精度）
    # from src.vision.yolo_vision import YOLOVision
    # vision_v3 = YOLOVision()
    # bridge_v3 = VisionControlBridge(vision_v3)

    print("✅ 只需替换 vision_system 实例，控制代码无需修改！")
    print("   这就是接口解耦的威力。")


# ==========================================
# 主函数
# ==========================================

if __name__ == "__main__":
    # 运行完整集成示例
    example_full_integration()

    # 展示算法替换
    # example_vision_algorithm_replacement()
