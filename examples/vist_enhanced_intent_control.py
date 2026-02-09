"""
VIST Enhanced Intent Detection Integration Example

This example demonstrates how to integrate the enhanced intent detector
with conflict detection (β term) into the VIST system.

Key Features:
- Conflict detection for compliant takeover
- 5-stage state machine
- Dynamic α adjustment based on human-algorithm disagreement

Author: VIST Team
Date: 2026-02-09
"""

import os
import sys
import numpy as np

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.intent_detector import (
    EnhancedIntentDetector,
    IntentState,
    IntentDetectionResult,
    compute_human_command,
    compute_algorithm_expectation
)
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.motion_mapper import ArmMotionMapper
from src.perception.target_detector import create_target_detector
from src.config.config import VISTConfig
from src.core.safety_monitor_simplified import SimplifiedSafetyMonitor


class VISTEnhancedController:
    """
    VIST 增强控制器（带冲突检测）

    核心创新：
    1. 冲突检测（β term）：检测人类-算法意图冲突
    2. 修正的意图因子：α_effective = α × (1-β)
    3. Compliant takeover：人类可以随时接管控制
    """

    def __init__(self, config: VISTConfig):
        """
        初始化 VIST 增强控制器

        Args:
            config: VIST 配置对象
        """
        self.config = config

        # 初始化组件
        self.intent_detector = EnhancedIntentDetector(config)
        self.motion_mapper = ArmMotionMapper(config)
        self.target_detector = create_target_detector('apriltag', config)
        self.vist_filter = VISTKalmanFilter(config)

        # 初始化简化安全监控器（兜底保护）
        config_max_velocity = getattr(config, 'max_velocity', 0.10)  # 默认 10cm/s
        self.safety_monitor = SimplifiedSafetyMonitor(config_max_velocity)

        # 状态变量
        self.current_pos = np.zeros(3)
        self.current_velocity = np.zeros(3)
        self.target_socket_pos = None

        print("🚀 [VISTEnhancedController] 初始化完成")

    def update(self, human_keypoints: dict, robot_state: dict) -> dict:
        """
        主更新循环

        Args:
            human_keypoints: 人类关键点数据
            robot_state: 机器人状态数据

        Returns:
            control_command: 控制指令
        """
        # 1. 获取机器人当前状态
        self.current_pos = robot_state['end_effector_position']
        self.current_velocity = robot_state['end_effector_velocity']

        # 2. 检测目标位置
        if self.target_socket_pos is None:
            target_result = self.target_detector.detect()
            if target_result is not None:
                self.target_socket_pos = target_result.position
                print(f"🎯 [Controller] 检测到目标位置: {self.target_socket_pos}")

        # 3. 计算人类指令
        human_target_pos, human_target_quat, _ = self.motion_mapper.human_to_robot(human_keypoints)
        human_command = compute_human_command(
            self.current_pos,
            human_target_pos,
            self.current_velocity
        )

        # 4. 计算算法期望（虚拟夹具）
        if self.target_socket_pos is not None:
            algorithm_expectation = compute_algorithm_expectation(
                self.current_pos,
                self.target_socket_pos,
                virtual_fixture_gain=1.0
            )
        else:
            algorithm_expectation = np.zeros(3)

        # 5. 意图检测（带冲突检测）
        distance = np.linalg.norm(self.target_socket_pos - self.current_pos) if self.target_socket_pos is not None else 1.0
        velocity = np.linalg.norm(self.current_velocity)
        alignment_error = self._compute_alignment_error()

        intent_result = self.intent_detector.detect_intent(
            distance=distance,
            velocity=velocity,
            human_command=human_command,
            algorithm_expectation=algorithm_expectation,
            alignment_error=alignment_error,
            current_depth=robot_state.get('insertion_depth', 0.0)
        )

        # 6. 根据状态和意图因子生成控制指令
        control_command = self._generate_control_command(
            intent_result,
            human_target_pos,
            human_target_quat
        )

        # 7. 安全检查（兜底保护）
        if 'velocity' in control_command:
            safe_velocity, is_safe, safety_msg = self.safety_monitor.check(
                self.current_pos,
                control_command['velocity']
            )
            if not is_safe:
                print(f"🚨 [Controller] 安全检查失败: {safety_msg}")
                return {'mode': 'emergency_stop'}
            control_command['velocity'] = safe_velocity
            if safety_msg:  # 有警告消息
                print(f"⚠️ [Controller] {safety_msg}")

        # 8. 日志输出
        self._log_status(intent_result)

        return control_command

    def _generate_control_command(
        self,
        intent_result: IntentDetectionResult,
        human_target_pos: np.ndarray,
        human_target_quat: np.ndarray
    ) -> dict:
        """
        生成控制指令

        Args:
            intent_result: 意图检测结果
            human_target_pos: 人类目标位置
            human_target_quat: 人类目标姿态

        Returns:
            control_command: 控制指令
        """
        state = intent_result.state
        alpha_eff = intent_result.alpha_effective

        if state == IntentState.APPROACHING:
            # 阶段 1: 人类主导接近
            # α_eff ≈ 0，完全跟随人类指令
            target_pos = human_target_pos
            target_quat = human_target_quat

        elif state == IntentState.VISUAL_ADMITTANCE:
            # 阶段 2: 视觉导纳（算法主导）
            # α_eff ≈ 1，虚拟夹具引导
            # 但如果检测到冲突（β > 0），α_eff 会降低，允许人类接管
            target_pos = self._blend_targets(
                human_target_pos,
                self.target_socket_pos,
                alpha_eff
            )
            target_quat = human_target_quat

        elif state == IntentState.CORRECTION_OVERRIDE:
            # 阶段 3: 修正/接管（人类接管）
            # α_eff ≈ 0.2，主要跟随人类，保留少量算法辅助
            target_pos = self._blend_targets(
                human_target_pos,
                self.target_socket_pos,
                alpha_eff
            )
            target_quat = human_target_quat

        elif state == IntentState.CONSTRAINED_INSERTION:
            # 阶段 4: 约束插入（算法主导）
            # α_eff = 1，完全由算法控制
            insertion_velocity = self._compute_insertion_velocity(intent_result.distance)
            return {
                'mode': 'velocity_control',
                'velocity': insertion_velocity,
                'orientation': human_target_quat
            }

        elif state == IntentState.RELEASE:
            # 阶段 5: 释放（任务完成）
            return {
                'mode': 'release',
                'action': 'open_gripper_and_retract'
            }

        else:
            target_pos = human_target_pos
            target_quat = human_target_quat

        # 使用 VIST 卡尔曼滤波器求解
        joint_angles = self.vist_filter.solve(
            target_pos=target_pos,
            target_quat=target_quat,
            alpha=alpha_eff  # 使用有效意图因子
        )

        return {
            'mode': 'position_control',
            'joint_angles': joint_angles,
            'alpha_effective': alpha_eff,
            'beta': intent_result.beta
        }

    def _blend_targets(
        self,
        human_target: np.ndarray,
        algorithm_target: np.ndarray,
        alpha: float
    ) -> np.ndarray:
        """
        混合人类目标和算法目标

        Args:
            human_target: 人类目标位置
            algorithm_target: 算法目标位置
            alpha: 意图因子

        Returns:
            blended_target: 混合目标位置
        """
        if algorithm_target is None:
            return human_target

        # 线性混合
        blended_target = (1 - alpha) * human_target + alpha * algorithm_target

        return blended_target

    def _compute_insertion_velocity(self, remaining_depth: float) -> np.ndarray:
        """
        计算插入速度（分段控制）

        Args:
            remaining_depth: 剩余插入深度

        Returns:
            velocity: 插入速度向量
        """
        # 分段速度控制
        if remaining_depth > 0.010:  # > 10mm
            speed = 0.01  # 1cm/s（快速）
        elif remaining_depth > 0.005:  # 5-10mm
            speed = 0.005  # 0.5cm/s（中速）
        else:  # < 5mm
            speed = 0.002  # 0.2cm/s（慢速）

        # 插入方向（假设沿 Z 轴）
        direction = np.array([0, 0, 1])
        velocity = direction * speed

        return velocity

    def _compute_alignment_error(self) -> float:
        """
        计算对齐误差

        Returns:
            alignment_error: 对齐误差（米）
        """
        if self.target_socket_pos is None:
            return 1.0

        # 简单的欧氏距离
        error = np.linalg.norm(self.target_socket_pos - self.current_pos)

        return error

    def _log_status(self, intent_result: IntentDetectionResult):
        """
        日志输出

        Args:
            intent_result: 意图检测结果
        """
        print(f"\n{'='*60}")
        print(f"[VIST Enhanced Controller Status]")
        print(f"  State: {intent_result.state.value}")
        print(f"  α (base): {intent_result.alpha:.3f}")
        print(f"  β (conflict): {intent_result.beta:.3f}")
        print(f"  α_eff (effective): {intent_result.alpha_effective:.3f}")
        print(f"  Distance: {intent_result.distance*1000:.1f} mm")
        print(f"  Velocity: {intent_result.velocity*100:.1f} cm/s")
        print(f"  Alignment Error: {intent_result.alignment_error*1000:.1f} mm")
        print(f"  Confidence: {intent_result.confidence:.3f}")

        # 冲突警告
        if intent_result.beta > 0.3:
            print(f"  ⚠️  检测到意图冲突！人类正在接管控制")

        print(f"{'='*60}\n")


def main():
    """主函数"""
    # 加载配置
    config = VISTConfig()

    # 创建控制器
    controller = VISTEnhancedController(config)

    print("🚀 VIST Enhanced Controller with Conflict Detection")
    print("   Press Ctrl+C to stop\n")

    # 主循环（示例）
    try:
        while True:
            # 获取人类关键点（示例数据）
            human_keypoints = {
                'shoulder': np.array([0.0, 0.0, 0.0]),
                'elbow': np.array([0.1, 0.0, -0.1]),
                'wrist': np.array([0.2, 0.0, -0.2]),
                'index_mcp': np.array([0.22, 0.02, -0.22]),
                'pinky_mcp': np.array([0.22, -0.02, -0.22])
            }

            # 获取机器人状态（示例数据）
            robot_state = {
                'end_effector_position': np.array([0.3, 0.0, 0.2]),
                'end_effector_velocity': np.array([0.01, 0.0, -0.01]),
                'insertion_depth': 0.0
            }

            # 更新控制器
            control_command = controller.update(human_keypoints, robot_state)

            # 发送控制指令（示例）
            print(f"Control Command: {control_command['mode']}")

            # 模拟延时
            import time
            time.sleep(0.033)  # 30Hz

    except KeyboardInterrupt:
        print("\n✅ Controller stopped")


if __name__ == "__main__":
    main()
