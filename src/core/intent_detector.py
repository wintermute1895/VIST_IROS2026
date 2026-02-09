"""
VIST Intent Detection Module

This module implements enhanced intent detection with conflict detection (β term)
for human-algorithm shared control.

Key Features:
- 5-stage state machine (Approach, Visual Admittance, Correction/Override, Constrained Insertion, Release)
- Conflict detection: β term for detecting human-algorithm disagreement
- Modified α formula: α_effective = α × (1-β)
- Compliant takeover for micro-adjustments

Author: VIST Team
Date: 2026-02-09
"""

import numpy as np
from enum import Enum
from typing import Tuple, Optional
from dataclasses import dataclass


class IntentState(Enum):
    """意图状态枚举"""
    APPROACHING = "approaching"          # 接近阶段（人类主导）
    VISUAL_ADMITTANCE = "visual_admittance"  # 视觉导纳阶段（算法主导）
    CORRECTION_OVERRIDE = "correction_override"  # 修正/接管阶段（人类微调）
    CONSTRAINED_INSERTION = "constrained_insertion"  # 约束插入阶段（算法主导）
    RELEASE = "release"                  # 释放阶段（任务完成）


@dataclass
class IntentDetectionResult:
    """意图检测结果"""
    state: IntentState          # 当前状态
    alpha: float                # 基础意图因子 (0=人类主导, 1=算法主导)
    beta: float                 # 冲突因子 (0=无冲突, 1=完全冲突)
    alpha_effective: float      # 有效意图因子 α_eff = α × (1-β)
    confidence: float           # 检测置信度
    distance: float             # 到目标的距离
    velocity: float             # 移动速度
    alignment_error: float      # 对齐误差


class EnhancedIntentDetector:
    """
    增强的意图检测器（带冲突检测）

    核心创新：
    1. 冲突检测（β term）：检测人类-算法意图冲突
    2. 修正的意图因子：α_effective = α × (1-β)
    3. 5-stage state machine with compliant takeover

    公式：
        α = f(v, d)           # 基于速度和距离的基础意图因子
        β = conflict(...)     # 冲突因子（人类"抵抗"算法）
        α_eff = α × (1-β)     # 有效意图因子

    当 β 接近 1 时（人类强烈抵抗），α_eff → 0（人类接管）
    """

    def __init__(self, config=None):
        """
        初始化意图检测器

        Args:
            config: 配置对象（可选）
        """
        self.current_state = IntentState.APPROACHING

        # 阶段转换阈值（带迟滞）
        # 🚨 修正隐患三：迟滞逻辑 (Hysteresis/Schmidt Trigger)
        # 进入和退出的阈值不同，避免边界抖动
        self.align_distance_enter = 0.045  # 4.5cm，进入视觉导纳阶段（更严格）
        self.align_distance_exit = 0.055   # 5.5cm，退出视觉导纳阶段（更宽松）
        self.insertion_alignment_threshold = 0.002  # 2mm，开始插入

        # 微调/修正检测参数
        self.correction_velocity_threshold = 0.01  # 1cm/s
        self.correction_max_distance = 0.02  # 2cm
        self.correction_max_acceleration = 0.05  # 低加速度

        # 冲突检测参数
        self.conflict_angle_threshold = np.deg2rad(30)  # 30度
        self.conflict_velocity_threshold = 0.005  # 0.5cm/s

        # 插入控制参数
        self.insertion_target_depth = 0.015  # 15mm（USB 标准）
        self.insertion_current_depth = 0.0

        # 历史数据（用于计算加速度和冲突）
        self.prev_velocity = None
        self.prev_human_command = None
        self.prev_algorithm_expectation = None

        print("🎯 [EnhancedIntentDetector] 初始化完成")
        print(f"   初始状态: {self.current_state.value}")

    def detect_intent(
        self,
        distance: float,
        velocity: float,
        human_command: np.ndarray,
        algorithm_expectation: np.ndarray,
        alignment_error: float,
        current_depth: float = 0.0
    ) -> IntentDetectionResult:
        """
        检测当前意图状态（带冲突检测）

        Args:
            distance: 到目标的距离（米）
            velocity: 移动速度（米/秒）
            human_command: 人类指令向量 (3D)
            algorithm_expectation: 算法期望向量 (3D)
            alignment_error: 对齐误差（米）
            current_depth: 当前插入深度（米）

        Returns:
            IntentDetectionResult: 意图检测结果
        """
        # 计算加速度
        acceleration = self._compute_acceleration(velocity)

        # 状态转换逻辑
        self._update_state(distance, velocity, acceleration, alignment_error, current_depth)

        # 计算基础意图因子 α
        alpha = self._compute_alpha(self.current_state, distance, velocity)

        # 计算冲突因子 β（关键创新）
        beta = self._compute_conflict(human_command, algorithm_expectation, velocity)

        # 计算有效意图因子 α_eff = α × (1-β)
        alpha_effective = alpha * (1 - beta)

        # 计算置信度
        confidence = self._compute_confidence(distance, velocity, alignment_error)

        # 更新历史数据
        self.prev_velocity = velocity
        self.prev_human_command = human_command.copy() if human_command is not None else None
        self.prev_algorithm_expectation = algorithm_expectation.copy() if algorithm_expectation is not None else None

        return IntentDetectionResult(
            state=self.current_state,
            alpha=alpha,
            beta=beta,
            alpha_effective=alpha_effective,
            confidence=confidence,
            distance=distance,
            velocity=velocity,
            alignment_error=alignment_error
        )

    def _update_state(
        self,
        distance: float,
        velocity: float,
        acceleration: float,
        alignment_error: float,
        current_depth: float
    ):
        """
        更新状态机（带迟滞逻辑）

        状态转换：
        1. APPROACHING → VISUAL_ADMITTANCE: 距离 < 4.5cm（进入阈值）
        2. VISUAL_ADMITTANCE → APPROACHING: 距离 > 5.5cm（退出阈值，迟滞）
        3. VISUAL_ADMITTANCE → CORRECTION_OVERRIDE: 检测到人类修正意图
        4. CORRECTION_OVERRIDE → VISUAL_ADMITTANCE: 修正完成
        5. VISUAL_ADMITTANCE → CONSTRAINED_INSERTION: 对齐完成（误差 < 2mm）
        6. CONSTRAINED_INSERTION → RELEASE: 插入完成
        """
        if self.current_state == IntentState.APPROACHING:
            # 接近 → 视觉导纳（使用进入阈值）
            if distance < self.align_distance_enter:
                self.current_state = IntentState.VISUAL_ADMITTANCE
                print("🎯 [Intent] 进入视觉导纳阶段（算法主导）")

        elif self.current_state == IntentState.VISUAL_ADMITTANCE:
            # 🚨 修正隐患三：迟滞逻辑
            # 视觉导纳 → 接近（使用退出阈值，避免抖动）
            if distance > self.align_distance_exit:
                self.current_state = IntentState.APPROACHING
                print("🔙 [Intent] 退出视觉导纳，返回接近阶段")

            # 视觉导纳 → 修正/接管
            elif self._detect_correction_intent(velocity, acceleration, distance):
                self.current_state = IntentState.CORRECTION_OVERRIDE
                print("🔧 [Intent] 检测到修正意图（人类接管）")

            # 视觉导纳 → 约束插入
            elif alignment_error < self.insertion_alignment_threshold:
                self.current_state = IntentState.CONSTRAINED_INSERTION
                self.insertion_current_depth = 0.0  # 重置插入深度
                print("📥 [Intent] 开始约束插入（算法主导）")

        elif self.current_state == IntentState.CORRECTION_OVERRIDE:
            # 修正/接管 → 视觉导纳
            if not self._detect_correction_intent(velocity, acceleration, distance):
                self.current_state = IntentState.VISUAL_ADMITTANCE
                print("🎯 [Intent] 恢复视觉导纳阶段（算法主导）")

        elif self.current_state == IntentState.CONSTRAINED_INSERTION:
            # 🚨 修正隐患四：插入阶段保留"后悔药"
            # 即使在插入阶段，也要检测强烈的回拉动作
            # 如果检测到人类强烈反向拉动，立即中止插入

            # 约束插入 → 释放（正常完成）
            self.insertion_current_depth = current_depth
            if self._detect_insertion_complete(current_depth):
                self.current_state = IntentState.RELEASE
                print("✅ [Intent] 插入完成，等待释放")

            # 约束插入 → 修正/接管（紧急退出）
            # 检测强烈的反向拉动（速度快 + 加速度大）
            elif self._detect_emergency_pullback(velocity, acceleration):
                self.current_state = IntentState.CORRECTION_OVERRIDE
                print("⚠️ [Intent] 检测到紧急回拉，中止插入！")

    def _compute_alpha(
        self,
        state: IntentState,
        distance: float,
        velocity: float
    ) -> float:
        """
        计算基础意图因子 α

        α = 0: 人类主导（跟随人类指令）
        α = 1: 算法主导（虚拟夹具引导）

        Args:
            state: 当前状态
            distance: 到目标的距离
            velocity: 移动速度

        Returns:
            alpha: 意图因子 [0, 1]
        """
        if state == IntentState.APPROACHING:
            # 接近阶段：α → 0（人类主导）
            return 0.0

        elif state == IntentState.VISUAL_ADMITTANCE:
            # 视觉导纳阶段：α → 1（算法主导）
            # 可以根据距离和速度动态调整
            # α = f(v, d)
            return 1.0

        elif state == IntentState.CORRECTION_OVERRIDE:
            # 修正/接管阶段：α 降低（人类接管）
            # 但仍保留一定的算法辅助（平滑滤波）
            return 0.2  # 保留 20% 的算法辅助

        elif state == IntentState.CONSTRAINED_INSERTION:
            # 约束插入阶段：α = 1（算法主导）
            return 1.0

        elif state == IntentState.RELEASE:
            # 释放阶段：α = 0（人类主导）
            return 0.0

        return 0.5  # 默认值

    def _compute_conflict(
        self,
        human_command: np.ndarray,
        algorithm_expectation: np.ndarray,
        velocity: float
    ) -> float:
        """
        计算冲突因子 β（关键创新）

        β 表示人类-算法意图冲突程度：
        - β = 0: 无冲突（人类和算法方向一致）
        - β = 1: 完全冲突（人类和算法方向相反）

        计算方法：
        1. 计算人类指令和算法期望的夹角 θ
        2. 计算人类移动速度（表示"抵抗"强度）
        3. β = f(θ, v)

        当 β 接近 1 时，α_eff = α × (1-β) → 0，人类接管控制

        Args:
            human_command: 人类指令向量 (3D)
            algorithm_expectation: 算法期望向量 (3D)
            velocity: 人类移动速度

        Returns:
            beta: 冲突因子 [0, 1]
        """
        # 只在算法主导阶段计算冲突
        if self.current_state not in [IntentState.VISUAL_ADMITTANCE, IntentState.CONSTRAINED_INSERTION]:
            return 0.0

        # 检查输入有效性
        if human_command is None or algorithm_expectation is None:
            return 0.0

        # 🚨 修正隐患一：零速奇异点保护
        # 速度死区 (Deadband)：如果速度太慢，认为没有明确方向，不计算冲突
        VELOCITY_DEADBAND = 0.005  # 5mm/s

        human_norm = np.linalg.norm(human_command)
        algo_norm = np.linalg.norm(algorithm_expectation)

        # 死区保护：速度太小时，MediaPipe 噪声会导致方向向量疯狂乱跳
        if human_norm < VELOCITY_DEADBAND or algo_norm < 1e-6:
            # 速度太小，无法判断冲突，返回 0（无冲突）
            return 0.0

        human_dir = human_command / human_norm
        algo_dir = algorithm_expectation / algo_norm

        # 计算夹角 θ（使用点积）
        cos_theta = np.clip(np.dot(human_dir, algo_dir), -1.0, 1.0)
        theta = np.arccos(cos_theta)

        # 计算角度冲突分量（0 → 1）
        # θ = 0° → angle_conflict = 0（方向一致）
        # θ = 180° → angle_conflict = 1（方向相反）
        angle_conflict = theta / np.pi

        # 计算速度冲突分量（0 → 1）
        # 速度越大，表示人类"抵抗"越强
        velocity_conflict = np.clip(velocity / 0.05, 0.0, 1.0)  # 5cm/s 为最大

        # 综合冲突因子
        # 只有当角度差异大 AND 速度快时，才认为是真正的冲突
        if theta > self.conflict_angle_threshold and velocity > self.conflict_velocity_threshold:
            beta = angle_conflict * velocity_conflict
        else:
            beta = 0.0

        # 平滑处理（避免突变）
        beta = np.clip(beta, 0.0, 1.0)

        return beta

    def _detect_correction_intent(
        self,
        velocity: float,
        acceleration: float,
        distance: float
    ) -> bool:
        """
        检测人类修正/接管意图

        特征：
        - 小幅度移动（< 2cm）
        - 慢速度（< 1cm/s）
        - 低加速度（平稳移动）
        - 已经接近目标（< 5cm）

        Args:
            velocity: 移动速度
            acceleration: 加速度
            distance: 到目标的距离

        Returns:
            is_correction: 是否检测到修正意图
        """
        is_small_movement = distance < self.correction_max_distance
        is_slow_speed = velocity < self.correction_velocity_threshold
        is_smooth = acceleration < self.correction_max_acceleration
        is_near_target = distance < self.align_distance_enter  # 使用进入阈值

        return is_small_movement and is_slow_speed and is_smooth and is_near_target

    def _detect_insertion_complete(self, current_depth: float) -> bool:
        """
        检测插入完成

        条件：
        - 深度达到标准值（15mm）

        Args:
            current_depth: 当前插入深度（米）

        Returns:
            is_complete: 是否插入完成
        """
        depth_reached = current_depth >= self.insertion_target_depth * 0.95  # 95% 深度

        return depth_reached

    def _detect_emergency_pullback(
        self,
        velocity: float,
        acceleration: float
    ) -> bool:
        """
        检测紧急回拉（插入阶段的安全出口）

        🚨 修正隐患四：插入阶段必须保留"后悔药"
        如果在插入过程中，人类突然用力往回拉，系统必须立即中止插入

        特征：
        - 高速度（> 3cm/s）
        - 高加速度（> 0.2m/s²）
        - 表示人类强烈反对当前动作

        Args:
            velocity: 移动速度
            acceleration: 加速度

        Returns:
            is_pullback: 是否检测到紧急回拉
        """
        EMERGENCY_VELOCITY_THRESHOLD = 0.03  # 3cm/s
        EMERGENCY_ACCELERATION_THRESHOLD = 0.2  # 0.2m/s²

        is_fast = velocity > EMERGENCY_VELOCITY_THRESHOLD
        is_sudden = acceleration > EMERGENCY_ACCELERATION_THRESHOLD

        return is_fast and is_sudden

    def _compute_acceleration(self, velocity: float) -> float:
        """
        计算加速度（基于速度变化）

        Args:
            velocity: 当前速度

        Returns:
            acceleration: 加速度
        """
        if self.prev_velocity is None:
            return 0.0

        # 简单的差分计算
        # 假设采样频率为 30Hz
        dt = 1.0 / 30.0
        acceleration = abs(velocity - self.prev_velocity) / dt

        return acceleration

    def _compute_confidence(
        self,
        distance: float,
        velocity: float,
        alignment_error: float
    ) -> float:
        """
        计算检测置信度

        Args:
            distance: 到目标的距离
            velocity: 移动速度
            alignment_error: 对齐误差

        Returns:
            confidence: 置信度 [0, 1]
        """
        # 简单的置信度计算
        # 距离越近，置信度越高
        distance_confidence = 1.0 - np.clip(distance / 0.1, 0.0, 1.0)

        # 速度适中时，置信度越高
        velocity_confidence = 1.0 - abs(velocity - 0.01) / 0.05

        # 对齐误差越小，置信度越高
        alignment_confidence = 1.0 - np.clip(alignment_error / 0.01, 0.0, 1.0)

        # 综合置信度
        confidence = (distance_confidence + velocity_confidence + alignment_confidence) / 3.0

        return np.clip(confidence, 0.0, 1.0)

    def reset(self):
        """重置检测器状态"""
        self.current_state = IntentState.APPROACHING
        self.prev_velocity = None
        self.prev_human_command = None
        self.prev_algorithm_expectation = None
        self.insertion_current_depth = 0.0
        print("🔄 [EnhancedIntentDetector] 状态已重置")


# 辅助函数

def compute_human_command(
    current_pos: np.ndarray,
    target_pos: np.ndarray,
    velocity: np.ndarray
) -> np.ndarray:
    """
    计算人类指令向量

    Args:
        current_pos: 当前位置
        target_pos: 目标位置（从人类手部映射）
        velocity: 当前速度

    Returns:
        human_command: 人类指令向量
    """
    # 方法 1: 基于位置差
    position_command = target_pos - current_pos

    # 方法 2: 基于速度
    velocity_command = velocity

    # 综合（可以根据实际情况调整权重）
    human_command = position_command + velocity_command * 0.1

    return human_command


def compute_algorithm_expectation(
    current_pos: np.ndarray,
    target_socket_pos: np.ndarray,
    virtual_fixture_gain: float = 1.0
) -> np.ndarray:
    """
    计算算法期望向量（虚拟夹具）

    Args:
        current_pos: 当前位置
        target_socket_pos: 目标插孔位置
        virtual_fixture_gain: 虚拟夹具增益

    Returns:
        algorithm_expectation: 算法期望向量
    """
    # 虚拟夹具：朝向目标的吸引力
    direction_to_target = target_socket_pos - current_pos
    distance = np.linalg.norm(direction_to_target)

    if distance < 1e-6:
        return np.zeros(3)

    # 归一化方向
    direction_normalized = direction_to_target / distance

    # 算法期望：朝向目标移动
    algorithm_expectation = direction_normalized * virtual_fixture_gain

    return algorithm_expectation
