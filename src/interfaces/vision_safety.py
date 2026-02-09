#!/usr/bin/env python3
"""
视觉-控制安全握手层 (Vision-Control Safety Layer)

负责：
1. 数据有效性检查
2. 异常检测（陈旧、跳变、遮挡）
3. 安全策略（急停、降级、回退）

设计原则：
- 防御式编程：假设视觉数据可能出错
- 分层防御：多重安全检查
- 可配置：安全阈值可调整
"""

from typing import Optional, Tuple
from enum import Enum
import numpy as np
import time

from src.interfaces.vision_packet import VisionPacket, TrackingStatus


class SafetyAction(Enum):
    """安全动作枚举"""
    PASS = "pass"                    # 通过，数据安全
    WARNING = "warning"              # 警告，数据可疑但可用
    REJECT = "reject"                # 拒绝，数据不可用
    EMERGENCY_STOP = "emergency_stop"  # 紧急停止


class SafetyCheckResult:
    """安全检查结果"""

    def __init__(self, action: SafetyAction, reason: str = ""):
        self.action = action
        self.reason = reason
        self.timestamp = time.time()

    def is_safe(self) -> bool:
        """数据是否安全可用"""
        return self.action in [SafetyAction.PASS, SafetyAction.WARNING]

    def should_stop(self) -> bool:
        """是否应该触发急停"""
        return self.action == SafetyAction.EMERGENCY_STOP

    def __str__(self) -> str:
        return f"SafetyCheck({self.action.value}: {self.reason})"


class VisionSafetyLayer:
    """
    视觉数据安全层

    职责：
    1. 检测陈旧数据 (Stale Data)
    2. 检测目标跳变 (Teleportation)
    3. 检测遮挡 (Occlusion)
    4. 执行安全策略

    使用方式：
    ```python
    safety = VisionSafetyLayer()
    packet = vision_system.get_latest_frame()
    check_result = safety.check(packet)

    if check_result.should_stop():
        robot.emergency_stop()
    elif check_result.is_safe():
        control_system.update(packet)
    ```
    """

    def __init__(self, config=None):
        """
        初始化安全层

        Args:
            config: 配置对象（可选）
        """
        # 加载配置
        if config is None:
            from src.config import get_config
            config = get_config()

        self.config = config

        # ==========================================
        # 安全阈值（可配置）
        # ==========================================

        # 1. 陈旧数据检测
        self.max_data_age = getattr(config, 'vision_max_data_age', 0.1)  # 100ms

        # 2. 跳变检测
        self.max_position_jump = getattr(config, 'vision_max_position_jump', 0.2)  # 20cm
        self.max_velocity = getattr(config, 'vision_max_velocity', 2.0)  # 2m/s

        # 3. 置信度阈值
        self.min_confidence = getattr(config, 'vision_min_confidence', 0.5)
        self.critical_confidence = getattr(config, 'vision_critical_confidence', 0.3)

        # 4. 遮挡处理策略
        self.occlusion_strategy = getattr(config, 'vision_occlusion_strategy', 'reject')
        # 可选值: 'reject' (拒绝), 'last_known' (使用最后已知状态), 'extrapolate' (外推)

        # ==========================================
        # 历史数据（用于跳变检测）
        # ==========================================
        self.last_valid_packet: Optional[VisionPacket] = None
        self.last_wrist_position: Optional[np.ndarray] = None
        self.last_timestamp: Optional[float] = None

        # ==========================================
        # 统计信息
        # ==========================================
        self.total_checks = 0
        self.passed_checks = 0
        self.rejected_checks = 0
        self.emergency_stops = 0

        print("🛡️  [SafetyLayer] 初始化完成")
        print(f"   最大数据年龄: {self.max_data_age*1000:.0f}ms")
        print(f"   最大位置跳变: {self.max_position_jump*100:.0f}cm")
        print(f"   最大速度: {self.max_velocity:.1f}m/s")
        print(f"   最小置信度: {self.min_confidence:.2f}")

    def check(self, packet: Optional[VisionPacket]) -> SafetyCheckResult:
        """
        执行完整的安全检查

        Args:
            packet: 视觉数据包

        Returns:
            SafetyCheckResult: 检查结果
        """
        self.total_checks += 1

        # ==========================================
        # 检查 1: 数据包是否存在
        # ==========================================
        if packet is None:
            self.rejected_checks += 1
            return SafetyCheckResult(
                SafetyAction.REJECT,
                "数据包为空（视觉系统可能未启动或超时）"
            )

        # ==========================================
        # 检查 2: 数据是否陈旧 (Stale Data)
        # ==========================================
        if packet.is_stale(self.max_data_age):
            age_ms = packet.get_age() * 1000
            self.rejected_checks += 1
            return SafetyCheckResult(
                SafetyAction.REJECT,
                f"数据陈旧（年龄: {age_ms:.1f}ms > {self.max_data_age*1000:.0f}ms）"
            )

        # ==========================================
        # 检查 3: 追踪状态
        # ==========================================
        if packet.tracking_status == TrackingStatus.LOST:
            self.rejected_checks += 1
            return SafetyCheckResult(
                SafetyAction.REJECT,
                "目标丢失（tracking_status=LOST）"
            )

        # ==========================================
        # 检查 4: 关键点置信度
        # ==========================================
        confidence_check = self._check_confidence(packet)
        if not confidence_check.is_safe():
            self.rejected_checks += 1
            return confidence_check

        # ==========================================
        # 检查 5: 关键点有效性（NaN, Inf）
        # ==========================================
        validity_check = self._check_validity(packet)
        if not validity_check.is_safe():
            self.rejected_checks += 1
            return validity_check

        # ==========================================
        # 检查 6: 目标跳变 (Teleportation)
        # ==========================================
        if self.last_wrist_position is not None and self.last_timestamp is not None:
            jump_check = self._check_teleportation(packet)
            if not jump_check.is_safe():
                # 跳变可能触发急停
                if jump_check.should_stop():
                    self.emergency_stops += 1
                else:
                    self.rejected_checks += 1
                return jump_check

        # ==========================================
        # 检查 7: 遮挡处理 (Occlusion)
        # ==========================================
        if packet.tracking_status == TrackingStatus.OCCLUDED:
            occlusion_check = self._handle_occlusion(packet)
            if not occlusion_check.is_safe():
                self.rejected_checks += 1
                return occlusion_check

        # ==========================================
        # 所有检查通过
        # ==========================================
        self.passed_checks += 1

        # 更新历史数据
        self.last_valid_packet = packet
        self.last_wrist_position = packet.wrist.position.copy()
        self.last_timestamp = packet.timestamp

        return SafetyCheckResult(SafetyAction.PASS, "所有检查通过")

    def _check_confidence(self, packet: VisionPacket) -> SafetyCheckResult:
        """检查关键点置信度"""
        # 检查腕部置信度（最关键）
        if packet.wrist.confidence < self.critical_confidence:
            return SafetyCheckResult(
                SafetyAction.EMERGENCY_STOP,
                f"腕部置信度过低（{packet.wrist.confidence:.2f} < {self.critical_confidence:.2f}）"
            )

        if packet.wrist.confidence < self.min_confidence:
            return SafetyCheckResult(
                SafetyAction.REJECT,
                f"腕部置信度不足（{packet.wrist.confidence:.2f} < {self.min_confidence:.2f}）"
            )

        # 检查肘部置信度
        if packet.elbow.confidence < self.min_confidence:
            return SafetyCheckResult(
                SafetyAction.WARNING,
                f"肘部置信度不足（{packet.elbow.confidence:.2f}），但腕部可用"
            )

        return SafetyCheckResult(SafetyAction.PASS)

    def _check_validity(self, packet: VisionPacket) -> SafetyCheckResult:
        """检查关键点数值有效性（NaN, Inf）"""
        keypoints = {
            'wrist': packet.wrist,
            'elbow': packet.elbow,
            'shoulder': packet.shoulder,
            'index_mcp': packet.index_mcp,
            'pinky_mcp': packet.pinky_mcp
        }

        for name, kp in keypoints.items():
            if not np.all(np.isfinite(kp.position)):
                return SafetyCheckResult(
                    SafetyAction.EMERGENCY_STOP,
                    f"{name} 包含无效值（NaN或Inf）: {kp.position}"
                )

        return SafetyCheckResult(SafetyAction.PASS)

    def _check_teleportation(self, packet: VisionPacket) -> SafetyCheckResult:
        """检测目标跳变（瞬移）"""
        current_pos = packet.wrist.position
        last_pos = self.last_wrist_position
        dt = packet.timestamp - self.last_timestamp

        if dt < 1e-6:
            # 时间间隔太小，无法计算速度
            return SafetyCheckResult(SafetyAction.PASS)

        # 计算位置变化
        delta_pos = np.linalg.norm(current_pos - last_pos)

        # 检查 1: 位置跳变（绝对阈值）
        if delta_pos > self.max_position_jump:
            return SafetyCheckResult(
                SafetyAction.EMERGENCY_STOP,
                f"检测到位置跳变（{delta_pos*100:.1f}cm > {self.max_position_jump*100:.0f}cm）"
            )

        # 检查 2: 速度异常（相对阈值）
        velocity = delta_pos / dt
        if velocity > self.max_velocity:
            return SafetyCheckResult(
                SafetyAction.REJECT,
                f"速度异常（{velocity:.2f}m/s > {self.max_velocity:.1f}m/s）"
            )

        return SafetyCheckResult(SafetyAction.PASS)

    def _handle_occlusion(self, packet: VisionPacket) -> SafetyCheckResult:
        """处理遮挡情况"""
        if self.occlusion_strategy == 'reject':
            return SafetyCheckResult(
                SafetyAction.REJECT,
                "检测到遮挡（策略: reject）"
            )
        elif self.occlusion_strategy == 'last_known':
            # 使用最后已知状态（需要控制层实现）
            return SafetyCheckResult(
                SafetyAction.WARNING,
                "检测到遮挡（策略: last_known，使用历史数据）"
            )
        elif self.occlusion_strategy == 'extrapolate':
            # 外推（需要控制层实现）
            return SafetyCheckResult(
                SafetyAction.WARNING,
                "检测到遮挡（策略: extrapolate，使用预测数据）"
            )
        else:
            return SafetyCheckResult(
                SafetyAction.REJECT,
                f"未知的遮挡策略: {self.occlusion_strategy}"
            )

    def get_last_known_state(self) -> Optional[VisionPacket]:
        """
        获取最后已知的有效状态

        用于遮挡时的回退策略。

        Returns:
            Optional[VisionPacket]: 最后有效的数据包
        """
        return self.last_valid_packet

    def reset(self) -> None:
        """重置安全层状态"""
        self.last_valid_packet = None
        self.last_wrist_position = None
        self.last_timestamp = None
        print("🛡️  [SafetyLayer] 状态已重置")

    def get_statistics(self) -> dict:
        """获取统计信息"""
        pass_rate = (self.passed_checks / self.total_checks * 100) if self.total_checks > 0 else 0
        return {
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'rejected_checks': self.rejected_checks,
            'emergency_stops': self.emergency_stops,
            'pass_rate': pass_rate
        }

    def print_statistics(self) -> None:
        """打印统计信息"""
        stats = self.get_statistics()
        print("\n" + "="*60)
        print("🛡️  安全层统计信息")
        print("="*60)
        print(f"总检查次数: {stats['total_checks']}")
        print(f"通过: {stats['passed_checks']} ({stats['pass_rate']:.1f}%)")
        print(f"拒绝: {stats['rejected_checks']}")
        print(f"紧急停止: {stats['emergency_stops']}")
        print("="*60)
