"""
VIST Intent Detection Module (Paper-Aligned Implementation)

This module implements continuous intent factor calculation based on the paper
formulas (Eq. 2-5), replacing the legacy state machine approach.

Key Features:
- Continuous α calculation: α_geo × α_vel × α_dir
- Geometric factor: α_geo = exp(-0.5 * d²)
- Velocity factor: α_vel = 1 / (1 + β * v²) (Fitts' Law)
- Directional factor: α_dir = 0.5 * (1 + cos(θ))
- Smooth, differentiable transitions (no discrete jumps)

Author: VIST Team
Date: 2026-02-17 (Refactored to match paper)
"""

import numpy as np
from typing import Tuple, Dict, Optional
from dataclasses import dataclass


@dataclass
class IntentFactors:
    """意图因子分解（用于调试和可视化）"""
    alpha: float              # 综合意图因子 [0, 1]
    alpha_geo: float          # 几何距离因子
    alpha_vel: float          # 速度因子
    alpha_dir: float          # 方向对齐因子
    distance: float           # 到目标的距离（米）
    velocity_norm: float      # 速度范数（米/秒）
    alignment_angle: float    # 对齐角度（弧度）


class ContinuousIntentDetector:
    """
    连续意图检测器（符合论文公式）

    核心公式（论文 Eq. 2-5）：
        α_geo  = exp(-0.5 * d²_M)           # 几何距离因子（Eq. 2）
        α_vel  = 1 / (1 + β * v²)           # 速度因子（Eq. 3, Fitts' Law）
        α_dir  = 0.5 * (1 + cos(θ))         # 方向因子（Eq. 4）
        α      = α_geo × α_vel × α_dir      # 综合意图因子

    其中：
        d_M = sqrt(Δx^T W Δx)  # Mahalanobis 距离
        v   = ||velocity||      # 速度范数
        θ   = angle(velocity, direction_to_target)  # 方向夹角
    """

    def __init__(self, config=None):
        """
        初始化意图检测器

        Args:
            config: 配置对象（可选）
        """
        # 从配置加载参数（如果提供）
        if config is not None:
            self.W_task = np.diag(config.vist_w_task[:3])  # 任务空间权重矩阵
            self.beta = config.vist_alpha_beta             # 速度因子系数
            self.w_geo = config.vist_w_geo                 # 几何因子权重
            self.w_vel = config.vist_w_vel                 # 速度因子权重
            self.eta = config.vist_alpha_alignment_power   # 方向对齐幂次
        else:
            # 默认参数
            self.W_task = np.diag([1.0, 1.0, 1.0])  # 各向同性
            self.beta = 100.0                        # 速度敏感度
            self.w_geo = 0.6                         # 几何权重
            self.w_vel = 0.4                         # 速度权重
            self.eta = 2.0                           # 方向对齐幂次

        # 平滑滤波器（避免 α 突变）
        self.alpha_smoothed = 0.0
        self.smoothing_factor = 0.1  # 低通滤波系数（0.1 = 10% 新值，90% 旧值）

        print("🎯 [ContinuousIntentDetector] 初始化完成（论文公式）")
        print(f"   参数: β={self.beta}, w_geo={self.w_geo}, w_vel={self.w_vel}, η={self.eta}")

    def detect_intent(
        self,
        current_pos: np.ndarray,
        target_pos: np.ndarray,
        velocity: np.ndarray,
        smooth: bool = True
    ) -> IntentFactors:
        """
        检测当前意图因子（连续公式）

        Args:
            current_pos: 当前位置 (3D, 米)
            target_pos: 目标位置 (3D, 米)
            velocity: 当前速度 (3D, 米/秒)
            smooth: 是否应用平滑滤波

        Returns:
            IntentFactors: 意图因子及其分解
        """
        # 1. 计算几何距离因子 α_geo（Eq. 2）
        alpha_geo = self._compute_geometric_factor(current_pos, target_pos)

        # 2. 计算速度因子 α_vel（Eq. 3）
        alpha_vel = self._compute_velocity_factor(velocity)

        # 3. 计算方向对齐因子 α_dir（Eq. 4）
        alpha_dir, alignment_angle = self._compute_directional_factor(
            current_pos, target_pos, velocity
        )

        # 4. 融合意图因子（Eq. 5）
        alpha_raw = self._fuse_intent_factors(alpha_geo, alpha_vel, alpha_dir)

        # 5. 平滑滤波（可选）
        if smooth:
            alpha = self._smooth_alpha(alpha_raw)
        else:
            alpha = alpha_raw

        # 6. 计算辅助信息
        distance = np.linalg.norm(target_pos - current_pos)
        velocity_norm = np.linalg.norm(velocity)

        return IntentFactors(
            alpha=alpha,
            alpha_geo=alpha_geo,
            alpha_vel=alpha_vel,
            alpha_dir=alpha_dir,
            distance=distance,
            velocity_norm=velocity_norm,
            alignment_angle=alignment_angle
        )

    def _compute_geometric_factor(
        self,
        current_pos: np.ndarray,
        target_pos: np.ndarray
    ) -> float:
        """
        计算几何距离因子 α_geo（Eq. 2）

        公式：α_geo = exp(-0.5 * d²_M)
        其中：d_M = sqrt(Δx^T W Δx)  # Mahalanobis 距离

        Args:
            current_pos: 当前位置 (3D)
            target_pos: 目标位置 (3D)

        Returns:
            alpha_geo: 几何距离因子 [0, 1]
        """
        # 位置误差
        xi_err = target_pos - current_pos

        # Mahalanobis 距离平方
        mahalanobis_sq = xi_err.T @ self.W_task @ xi_err

        # 指数衰减
        alpha_geo = np.exp(-0.5 * mahalanobis_sq)

        return float(np.clip(alpha_geo, 0.0, 1.0))

    def _compute_velocity_factor(self, velocity: np.ndarray) -> float:
        """
        计算速度因子 α_vel（Eq. 3, Fitts' Law）

        公式：α_vel = 1 / (1 + β * v²)

        物理意义：
        - 速度快（v 大）→ α_vel 小 → 人类主导（自由移动）
        - 速度慢（v 小）→ α_vel 大 → 算法主导（精密对齐）

        Args:
            velocity: 速度向量 (3D, 米/秒)

        Returns:
            alpha_vel: 速度因子 [0, 1]
        """
        # 速度范数平方
        speed_sq = np.linalg.norm(velocity) ** 2

        # Fitts' Law 形式
        alpha_vel = 1.0 / (1.0 + self.beta * speed_sq)

        return float(np.clip(alpha_vel, 0.0, 1.0))

    def _compute_directional_factor(
        self,
        current_pos: np.ndarray,
        target_pos: np.ndarray,
        velocity: np.ndarray
    ) -> Tuple[float, float]:
        """
        计算方向对齐因子 α_dir（Eq. 4）

        公式：α_dir = 0.5 * (1 + cos(θ))

        其中：θ = angle(velocity, direction_to_target)

        物理意义：
        - θ = 0°（朝向目标）→ α_dir = 1.0 → 算法主导
        - θ = 90°（垂直移动）→ α_dir = 0.5 → 中性
        - θ = 180°（远离目标）→ α_dir = 0.0 → 人类主导

        Args:
            current_pos: 当前位置 (3D)
            target_pos: 目标位置 (3D)
            velocity: 速度向量 (3D)

        Returns:
            (alpha_dir, alignment_angle): 方向因子和对齐角度（弧度）
        """
        # 计算到目标的方向
        xi_err = target_pos - current_pos
        xi_err_norm = np.linalg.norm(xi_err)
        velocity_norm = np.linalg.norm(velocity)

        # 零速度或零距离保护
        if xi_err_norm < 1e-6 or velocity_norm < 1e-6:
            # 无法判断方向，返回中性值
            return 1.0, 0.0

        # 归一化方向向量
        direction_to_target = xi_err / xi_err_norm
        velocity_direction = velocity / velocity_norm

        # 计算夹角余弦值
        cos_theta = np.dot(velocity_direction, direction_to_target)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)

        # 计算方向因子
        alpha_dir = 0.5 * (1.0 + cos_theta)

        # 计算角度（用于调试）
        alignment_angle = np.arccos(cos_theta)

        return float(np.clip(alpha_dir, 0.0, 1.0)), float(alignment_angle)

    def _fuse_intent_factors(
        self,
        alpha_geo: float,
        alpha_vel: float,
        alpha_dir: float
    ) -> float:
        """
        融合意图因子（Eq. 5）

        公式（论文实现）：
            state_prior = w_geo * α_geo + w_vel * α_vel
            state_prior_normalized = sigmoid(5 * (state_prior - 0.5))
            active_gating = α_dir ^ η
            α = state_prior_normalized * active_gating

        Args:
            alpha_geo: 几何距离因子
            alpha_vel: 速度因子
            alpha_dir: 方向对齐因子

        Returns:
            alpha: 综合意图因子 [0, 1]
        """
        # 状态先验（几何 + 速度）
        state_prior = self.w_geo * alpha_geo + self.w_vel * alpha_vel

        # Sigmoid 归一化（增强对比度）
        state_prior_normalized = 1.0 / (1.0 + np.exp(-5.0 * (state_prior - 0.5)))

        # 主动门控（方向对齐的幂次）
        active_gating = alpha_dir ** self.eta

        # 最终意图因子
        alpha = state_prior_normalized * active_gating

        return float(np.clip(alpha, 0.0, 1.0))

    def _smooth_alpha(self, alpha_raw: float) -> float:
        """
        平滑意图因子（低通滤波）

        公式：α_smooth = (1-λ) * α_smooth_prev + λ * α_raw

        Args:
            alpha_raw: 原始意图因子

        Returns:
            alpha_smooth: 平滑后的意图因子
        """
        # 指数移动平均（EMA）
        self.alpha_smoothed = (
            (1.0 - self.smoothing_factor) * self.alpha_smoothed +
            self.smoothing_factor * alpha_raw
        )

        return self.alpha_smoothed

    def reset(self):
        """重置检测器状态"""
        self.alpha_smoothed = 0.0
        print("🔄 [ContinuousIntentDetector] 状态已重置")


# ============================================================================
# 向后兼容接口（保留旧的 EnhancedIntentDetector 接口）
# ============================================================================

class EnhancedIntentDetector(ContinuousIntentDetector):
    """
    向后兼容的意图检测器

    保留旧接口，但内部使用新的连续公式实现
    """

    def __init__(self, config=None):
        super().__init__(config)
        print("⚠️  [EnhancedIntentDetector] 使用论文公式实现（已弃用状态机）")

    def detect_intent(
        self,
        distance: float = None,
        velocity: float = None,
        human_command: np.ndarray = None,
        algorithm_expectation: np.ndarray = None,
        alignment_error: float = None,
        current_depth: float = 0.0,
        # 新接口参数
        current_pos: np.ndarray = None,
        target_pos: np.ndarray = None,
        velocity_vec: np.ndarray = None
    ):
        """
        向后兼容的检测接口

        优先使用新接口（current_pos, target_pos, velocity_vec）
        如果不提供，尝试从旧接口参数推断
        """
        # 如果提供了新接口参数，使用新实现
        if current_pos is not None and target_pos is not None and velocity_vec is not None:
            result = super().detect_intent(current_pos, target_pos, velocity_vec)

            # 转换为旧的返回格式（如果需要）
            from src.core.intent_detector_legacy import IntentDetectionResult, IntentState
            return IntentDetectionResult(
                state=IntentState.VISUAL_ADMITTANCE,  # 不再使用状态机
                alpha=result.alpha,
                beta=0.0,  # 冲突检测已移除
                alpha_effective=result.alpha,
                confidence=1.0,
                distance=result.distance,
                velocity=result.velocity_norm,
                alignment_error=0.0
            )
        else:
            # 旧接口：无法完整实现，返回警告
            print("⚠️  [EnhancedIntentDetector] 旧接口已弃用，请使用新接口")
            print("   新接口: detect_intent(current_pos, target_pos, velocity_vec)")
            return None


# ============================================================================
# 辅助函数（保留向后兼容）
# ============================================================================

def compute_human_command(
    current_pos: np.ndarray,
    target_pos: np.ndarray,
    velocity: np.ndarray
) -> np.ndarray:
    """
    计算人类指令向量（向后兼容）

    Args:
        current_pos: 当前位置
        target_pos: 目标位置
        velocity: 当前速度

    Returns:
        human_command: 人类指令向量
    """
    position_command = target_pos - current_pos
    velocity_command = velocity
    human_command = position_command + velocity_command * 0.1
    return human_command


def compute_algorithm_expectation(
    current_pos: np.ndarray,
    target_socket_pos: np.ndarray,
    virtual_fixture_gain: float = 1.0
) -> np.ndarray:
    """
    计算算法期望向量（向后兼容）

    Args:
        current_pos: 当前位置
        target_socket_pos: 目标插孔位置
        virtual_fixture_gain: 虚拟夹具增益

    Returns:
        algorithm_expectation: 算法期望向量
    """
    direction_to_target = target_socket_pos - current_pos
    distance = np.linalg.norm(direction_to_target)

    if distance < 1e-6:
        return np.zeros(3)

    direction_normalized = direction_to_target / distance
    algorithm_expectation = direction_normalized * virtual_fixture_gain

    return algorithm_expectation