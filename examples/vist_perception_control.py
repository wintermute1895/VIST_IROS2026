#!/usr/bin/env python3
"""
VIST 完整流程示例：目标感知 + 意图感知 + 导纳控制

流程：
1. 人体姿态检测 (MediaPipe) → 运动映射 → 目标位姿
2. 目标检测 (USB插口) → 目标位置
3. 意图感知 (距离+速度) → 意图因子 α
4. VIST 卡尔曼滤波 (α驱动) → 关节角度
5. 虚拟夹具/导纳控制 (α→1时) → 精密引导

对应 VIST_modeling_v2.md 的完整实现
"""

import sys
import os
import time
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.perception.target_detector import (
    ITargetDetector,
    ManualTargetDetector,
    create_target_detector
)
from src.core.motion_mapper import ArmMotionMapper
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.config import get_config


class VISTPerceptionController:
    """
    VIST 感知控制器

    集成目标检测、意图感知、卡尔曼滤波、虚拟夹具。
    """

    def __init__(
        self,
        target_detector: ITargetDetector,
        motion_mapper: ArmMotionMapper,
        vist_filter: VISTKalmanFilter,
        config=None
    ):
        """
        Args:
            target_detector: 目标检测器
            motion_mapper: 运动映射器
            vist_filter: VIST 卡尔曼滤波器
            config: 配置对象
        """
        self.target_detector = target_detector
        self.motion_mapper = motion_mapper
        self.vist_filter = vist_filter
        self.config = config or get_config()

        # 统计信息
        self.frame_count = 0
        self.alpha_history = []
        self.distance_history = []

        print("🎮 [VISTController] 初始化完成")

    def process_frame(self, human_kps: dict) -> tuple:
        """
        处理一帧数据

        Args:
            human_kps: 人体关键点字典
                      {'shoulder': [x,y,z], 'elbow': [x,y,z], 'wrist': [x,y,z], ...}

        Returns:
            tuple: (joint_angles, alpha, debug_info)
                - joint_angles: 关节角度 (7,)
                - alpha: 意图因子
                - debug_info: 调试信息字典
        """
        self.frame_count += 1
        debug_info = {}

        # ==========================================
        # 步骤 1: 运动映射（人体 → 机器人目标位姿）
        # ==========================================
        result = self.motion_mapper.human_to_robot(human_kps)
        if result is None:
            print(f"⚠️ [Frame {self.frame_count}] 运动映射失败")
            return None, 0.0, debug_info

        target_pos, target_quat, mapper_debug = result
        debug_info['target_pos'] = target_pos
        debug_info['target_quat'] = target_quat

        # ==========================================
        # 步骤 2: 目标检测（USB插口位置）
        # ==========================================
        target_result = self.target_detector.detect()
        if target_result is None or not target_result.is_valid():
            print(f"⚠️ [Frame {self.frame_count}] 目标检测失败")
            # 如果没有目标，仍然可以运行（纯跟随模式）
            goal_pos = None
        else:
            goal_pos = target_result.position
            debug_info['goal_pos'] = goal_pos
            debug_info['goal_confidence'] = target_result.confidence

        # ==========================================
        # 步骤 3: VIST 卡尔曼滤波 + 意图感知
        # ==========================================
        # VIST 内部会：
        # 1. 调用 detect_intent() 计算 α（基于距离和速度）
        # 2. 根据 α 调整协方差 Q 和 R
        # 3. 如果有目标位置，计算虚拟夹具（微分IK）
        # 4. 融合人类指令和虚拟引导

        joint_angles, success, error = self.vist_filter.solve(
            target_pos=target_pos,
            target_quat=target_quat,
            elbow_pos=human_kps['elbow'],
            shoulder_pos=human_kps['shoulder']
        )

        if not success:
            print(f"⚠️ [Frame {self.frame_count}] VIST 求解失败")
            return None, 0.0, debug_info

        # ==========================================
        # 步骤 4: 获取意图因子和统计信息
        # ==========================================
        alpha = self.vist_filter.alpha_smoothed
        self.alpha_history.append(alpha)

        # 计算距离（如果有目标）
        if goal_pos is not None:
            current_pos = self.vist_filter._get_current_end_effector_position()
            distance = np.linalg.norm(goal_pos - current_pos)
            self.distance_history.append(distance)
            debug_info['distance_to_goal'] = distance
        else:
            debug_info['distance_to_goal'] = None

        debug_info['alpha'] = alpha
        debug_info['error'] = error
        debug_info['joint_angles'] = joint_angles

        # ==========================================
        # 步骤 5: 打印状态（每10帧）
        # ==========================================
        if self.frame_count % 10 == 0:
            self._print_status(alpha, debug_info)

        return joint_angles, alpha, debug_info

    def _print_status(self, alpha: float, debug_info: dict):
        """打印当前状态"""
        distance = debug_info.get('distance_to_goal', None)
        error = debug_info.get('error', 0.0)

        print(f"\n[帧 {self.frame_count}] VIST 状态:")
        print(f"  意图因子 α: {alpha:.3f} {'(接近)' if alpha < 0.5 else '(精密)'}")

        if distance is not None:
            print(f"  目标距离: {distance*100:.1f}cm")

        print(f"  位置误差: {error*1000:.2f}mm")

    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            'frame_count': self.frame_count,
            'avg_alpha': np.mean(self.alpha_history) if self.alpha_history else 0.0,
            'avg_distance': np.mean(self.distance_history) if self.distance_history else 0.0,
            'alpha_history': self.alpha_history,
            'distance_history': self.distance_history
        }


# ==========================================
# 完整示例：VIST 感知控制流程
# ==========================================

def example_vist_perception_control():
    """
    完整的 VIST 感知控制示例

    演示：目标检测 → 意图感知 → 卡尔曼滤波 → 虚拟夹具
    """
    print("\n" + "="*60)
    print("🚀 VIST 感知控制完整流程示例")
    print("="*60)

    # ==========================================
    # 1. 初始化组件
    # ==========================================
    print("\n📦 步骤 1: 初始化组件")

    config = get_config()

    # 1.1 目标检测器（手动指定USB插口位置）
    target_detector = create_target_detector(
        detector_type='manual',
        target_position=[0.35, 0.0, 0.45]  # USB插口位置（示例）
    )
    target_detector.initialize()

    # 1.2 运动映射器
    motion_mapper = ArmMotionMapper()

    # 1.3 IK 求解器
    urdf_path = os.path.join(project_root, 'config', config.robot_model_urdf_file)

    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame=config.robot_model_end_effector_frame
    )

    # 1.4 VIST 卡尔曼滤波器
    vist_filter = VISTKalmanFilter(
        ik_solver=ik_solver,
        config=config
    )

    # 1.5 VIST 控制器
    controller = VISTPerceptionController(
        target_detector=target_detector,
        motion_mapper=motion_mapper,
        vist_filter=vist_filter,
        config=config
    )

    print("✅ 所有组件初始化完成")

    # ==========================================
    # 2. 模拟控制循环
    # ==========================================
    print("\n🔄 步骤 2: 运行控制循环（模拟数据）")
    print("-"*60)

    # 模拟人体关键点数据（肩部坐标系）
    # 模拟从远处接近USB插口的过程
    for i in range(30):
        # 模拟手臂从远处逐渐接近目标
        t = i / 30.0
        z_offset = 0.6 - 0.2 * t  # 从60cm逐渐接近到40cm

        human_kps = {
            'shoulder': np.array([0.0, 0.0, 0.0]),
            'elbow': np.array([0.0, 0.2, 0.3]),
            'wrist': np.array([0.0, 0.2, z_offset]),
            'index_mcp': np.array([0.0, 0.25, z_offset + 0.05]),
            'pinky_mcp': np.array([0.0, 0.15, z_offset + 0.05])
        }

        # 处理一帧
        result = controller.process_frame(human_kps)

        if result[0] is not None:
            joint_angles, alpha, debug_info = result

            # 模拟控制频率
            time.sleep(0.033)  # 30Hz

    # ==========================================
    # 3. 打印统计信息
    # ==========================================
    print("\n📊 步骤 3: 统计信息")
    print("-"*60)

    stats = controller.get_statistics()
    print(f"总帧数: {stats['frame_count']}")
    print(f"平均意图因子: {stats['avg_alpha']:.3f}")
    print(f"平均目标距离: {stats['avg_distance']*100:.1f}cm")

    # ==========================================
    # 4. 清理资源
    # ==========================================
    print("\n🧹 步骤 4: 清理资源")
    target_detector.cleanup()

    print("\n" + "="*60)
    print("✅ 示例完成")
    print("="*60)


if __name__ == "__main__":
    example_vist_perception_control()
