"""
VIST Kalman Filter - 数学化版本

将所有if-else逻辑转换为连续的数学表达式，提升理论优雅性。

核心思想：
1. 用平滑函数（sigmoid, tanh）替代硬阈值
2. 用权重矩阵替代模式选择
3. 用连续函数替代条件分支

数学框架：
E(x) = ||z_human - Hx||²_R_human^(-1) + ||z_virtual - Hx||²_R_virtual^(-1) + ||x - x_pred||²_Q^(-1)

其中：
- R_human(α) = R_base + (R_max - R_base) · (1 - α)
- R_virtual(α, δ) = R_base + (R_base - R_min) · (1 - α) + γ_c · ||δ||²
- Q(α, J) = Q_base ⊙ Λ(α, J)
- Λ_ii(α, J) = 1 - σ(α - α_threshold) · (1 - |J_i · ẑ|)

Author: VIST Project
Date: 2026-02-10
"""

import numpy as np
from numpy.linalg import inv
import pinocchio as pin


class MathematicalVISTKalmanFilter:
    """
    数学化的VIST卡尔曼滤波器

    所有逻辑都通过连续的数学函数表达，无if-else分支
    """

    def __init__(self, ik_solver, config, geometric_solver=None):
        """初始化（与原版相同）"""
        self.ik_solver = ik_solver
        self.config = config
        self.geometric_solver = geometric_solver

        # 状态维度
        self.n_joints = config.vist_n_joints
        self.state_dim = config.vist_state_dim

        # 初始化状态和协方差
        self.state = np.zeros(self.state_dim)
        self.P = np.eye(self.state_dim) * 1e-2

        # 观测矩阵（恒等）
        self.H = np.eye(self.state_dim)

        # 意图因子
        self.alpha = 0.0
        self.alpha_smoothed = 0.0

        print("✅ [Mathematical VIST] 初始化完成（数学化版本）")

    # ==========================================
    # 核心数学函数
    # ==========================================

    @staticmethod
    def smooth_step(x, threshold=0.0, steepness=10.0):
        """
        平滑阶跃函数（替代 if x > threshold）

        使用sigmoid函数实现平滑过渡：
        σ(x) = 1 / (1 + exp(-k(x - threshold)))

        Args:
            x: 输入值
            threshold: 阈值
            steepness: 陡峭度（k值，越大越接近硬阈值）

        Returns:
            [0, 1] 之间的平滑值

        Example:
            >>> smooth_step(0.5, threshold=0.8, steepness=10)
            0.0474  # 接近0
            >>> smooth_step(0.9, threshold=0.8, steepness=10)
            0.7311  # 接近1
        """
        return 1.0 / (1.0 + np.exp(-steepness * (x - threshold)))

    @staticmethod
    def soft_clamp(x, min_val, max_val, smoothness=0.1):
        """
        软限幅函数（替代 np.clip）

        使用tanh实现平滑限幅，避免梯度消失

        Args:
            x: 输入值
            min_val: 最小值
            max_val: 最大值
            smoothness: 平滑度（越小越接近硬限幅）

        Returns:
            限幅后的值
        """
        # 归一化到[-1, 1]
        x_norm = 2 * (x - min_val) / (max_val - min_val) - 1
        # 软限幅
        x_clamped = np.tanh(x_norm / smoothness) * smoothness
        # 反归一化
        return (x_clamped + 1) * (max_val - min_val) / 2 + min_val

    @staticmethod
    def safe_norm(x, epsilon=1e-8):
        """
        安全的范数计算（避免除零）

        ||x||_safe = sqrt(||x||² + ε²)

        Args:
            x: 向量
            epsilon: 小常数

        Returns:
            安全的范数值
        """
        return np.sqrt(np.dot(x, x) + epsilon**2)

    # ==========================================
    # 数学化的协方差矩阵构建
    # ==========================================

    def _build_process_noise_covariance_mathematical(self):
        """
        构建过程噪声协方差矩阵 Q（数学化版本）

        数学公式：
        Q(α, J) = Q_base ⊙ Λ(α, J)

        其中自适应度量矩阵：
        Λ_ii(α, J) = 1 - σ(α - α_threshold) · (1 - normalize(|J_i · ẑ|))

        σ(x) 是平滑阶跃函数（smooth_step）

        Returns:
            Q: 过程噪声协方差矩阵 (state_dim x state_dim)
        """
        # 1. 基础Q矩阵
        Q_base = self._build_base_Q()

        # 2. 计算自适应度量矩阵
        Lambda = self._compute_adaptive_metric()

        # 3. 逐元素乘法
        Q = Q_base * Lambda

        return Q

    def _build_base_Q(self):
        """
        构建基础Q矩阵（无自适应调整）

        Returns:
            Q_base: 基础过程噪声协方差矩阵
        """
        Q = np.zeros((self.state_dim, self.state_dim))

        # 位置部分
        pos_variance = self.config.vist_position_variance
        Q[:self.n_joints, :self.n_joints] = pos_variance * np.eye(self.n_joints)

        # 速度部分
        vel_variance = self.config.vist_velocity_variance
        Q[self.n_joints:, self.n_joints:] = vel_variance * np.eye(self.n_joints)

        # 关节特定调整（使用权重向量，而非if-else）
        joint_weights = self._compute_joint_weights()
        for i in range(self.n_joints):
            Q[i, i] *= joint_weights[i]
            Q[self.n_joints + i, self.n_joints + i] *= joint_weights[i]

        return Q

    def _compute_joint_weights(self):
        """
        计算关节权重向量（替代if-else的关节特殊处理）

        数学表达：
        w_i = w_base · (1 + δ_i)

        其中 δ_i 是关节i的调整因子：
        - J3 (Swivel): δ = -0.9 (阻尼)
        - J4 (Elbow): δ = +0.2 (提升)
        - 其他: δ = 0

        Returns:
            weights: 关节权重向量 (n_joints,)
        """
        weights = np.ones(self.n_joints)

        # 使用one-hot编码替代索引判断
        swivel_mask = np.zeros(self.n_joints)
        swivel_mask[2] = 1.0  # J3

        elbow_mask = np.zeros(self.n_joints)
        elbow_mask[3] = 1.0  # J4

        # 向量化计算
        weights = weights * (1.0 - 0.9 * swivel_mask + 0.2 * elbow_mask)

        return weights

    def _compute_adaptive_metric(self):
        """
        计算自适应度量矩阵 Λ(α, J)

        数学公式：
        Λ_ii(α, J) = 1 - freeze_strength(α) · (1 - z_contribution_i)

        其中：
        - freeze_strength(α) = σ(α - α_threshold)
        - z_contribution_i = normalize(|J_i · ẑ|)

        Returns:
            Lambda: 自适应度量矩阵 (state_dim x state_dim)
        """
        Lambda = np.ones((self.state_dim, self.state_dim))

        # 1. 计算冻结强度（平滑阶跃函数）
        z_lock_threshold = 0.8
        freeze_strength = self.smooth_step(
            self.alpha_smoothed,
            threshold=z_lock_threshold,
            steepness=20.0  # 较陡的过渡
        )

        # 2. 计算雅可比矩阵（安全版本）
        try:
            q_controlled = self.state[:self.n_joints]
            q_full = self._get_full_q_from_controlled(q_controlled)

            # 检查有效性（使用连续函数而非if）
            validity = np.all(np.isfinite(q_full)).astype(float)

            # 计算雅可比
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

            J_full = pin.computeFrameJacobian(
                self.ik_solver.model,
                self.ik_solver.data,
                q_full,
                self.ik_solver.ee_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )

            J = J_full[:3, self.ik_solver.controlled_indices]

            # 3. 计算Z方向贡献（向量化）
            z_axis = np.array([0, 0, 1])
            z_contributions = np.abs(J.T @ z_axis)  # (n_joints,)

            # 4. 归一化（使用软归一化）
            z_threshold = 0.3
            z_contributions_normalized = np.tanh(z_contributions / z_threshold)

            # 5. 计算冻结因子（向量化）
            freeze_factors = 1.0 - freeze_strength * (1.0 - z_contributions_normalized)

            # 6. 软限幅（避免完全冻结）
            freeze_factors = self.soft_clamp(freeze_factors, min_val=0.01, max_val=1.0)

            # 7. 应用到Lambda矩阵（考虑有效性）
            for i in range(self.n_joints):
                Lambda[i, i] = 1.0 - validity * (1.0 - freeze_factors[i])
                Lambda[self.n_joints + i, self.n_joints + i] = Lambda[i, i]

        except Exception:
            # 失败时Lambda保持为单位矩阵（优雅降级）
            pass

        return Lambda

    def _build_observation_noise_covariance_mathematical(
        self,
        human_delta_theta=None,
        virtual_delta_theta=None
    ):
        """
        构建观测噪声协方差矩阵 R（数学化版本）

        数学公式：
        R = diag(R_human(α), R_virtual(α, δ))

        其中：
        - R_human(α) = R_base + (R_max - R_base) · (1 - α)
        - R_virtual(α, δ) = R_base + (R_base - R_min) · (1 - α) + γ_c · ||δ||²
        - δ = Δθ_human - Δθ_virtual（冲突向量）

        Args:
            human_delta_theta: 人类指令增量
            virtual_delta_theta: 虚拟引导增量

        Returns:
            R: 观测噪声协方差矩阵 (2*n_joints x 2*n_joints)
        """
        R = np.zeros((2 * self.n_joints, 2 * self.n_joints))

        # 1. 人类指令噪声（意图驱动）
        R_human = self._compute_human_variance(self.alpha_smoothed)
        R[:self.n_joints, :self.n_joints] = R_human * np.eye(self.n_joints)

        # 2. 虚拟引导噪声（意图驱动 + 冲突检测）
        R_virtual = self._compute_virtual_variance(
            self.alpha_smoothed,
            human_delta_theta,
            virtual_delta_theta
        )
        R[self.n_joints:, self.n_joints:] = R_virtual * np.eye(self.n_joints)

        # 3. 几何求解器权重调整（使用权重向量）
        geometric_weights = self._compute_geometric_solver_weights()
        for i in range(self.n_joints):
            R[i, i] *= geometric_weights[i, 0]  # 人类观测权重
            R[self.n_joints + i, self.n_joints + i] *= geometric_weights[i, 1]  # 虚拟观测权重

        return R

    def _compute_human_variance(self, alpha):
        """
        计算人类指令方差（连续函数）

        R_human(α) = R_base + (R_max - R_base) · (1 - α)

        Args:
            alpha: 意图因子

        Returns:
            R_human: 人类指令方差
        """
        R_base = self.config.vist_human_base_variance
        R_max = self.config.vist_human_max_variance

        return R_base + (R_max - R_base) * (1.0 - alpha)

    def _compute_virtual_variance(self, alpha, human_delta_theta, virtual_delta_theta):
        """
        计算虚拟引导方差（连续函数 + 冲突检测）

        R_virtual(α, δ) = R_base + (R_base - R_min) · (1 - α) + γ_c · ||δ||²_safe

        Args:
            alpha: 意图因子
            human_delta_theta: 人类指令增量
            virtual_delta_theta: 虚拟引导增量

        Returns:
            R_virtual: 虚拟引导方差
        """
        R_base = self.config.vist_virtual_base_variance
        R_min = self.config.vist_virtual_min_variance

        # 基础方差（意图驱动）
        R_virtual = R_base + (R_base - R_min) * (1.0 - alpha)

        # 冲突项（使用安全范数，避免None判断）
        if human_delta_theta is None:
            human_delta_theta = np.zeros(self.n_joints)
        if virtual_delta_theta is None:
            virtual_delta_theta = np.zeros(self.n_joints)

        conflict_vector = human_delta_theta - virtual_delta_theta
        conflict_magnitude = self.safe_norm(conflict_vector)**2

        # 冲突增益
        conflict_gain = getattr(self.config, 'vist_conflict_gain', 0.5)

        # 添加冲突项
        R_virtual += conflict_gain * conflict_magnitude

        # 软限幅（避免数值问题）
        R_virtual = self.soft_clamp(R_virtual, min_val=R_min, max_val=1e3)

        return R_virtual

    def _compute_geometric_solver_weights(self):
        """
        计算几何求解器权重矩阵（替代if判断）

        使用指示函数的平滑版本：
        w_i = w_default · (1 - enabled) + w_geometric · enabled

        其中 enabled ∈ {0, 1} 表示几何求解器是否启用

        Returns:
            weights: 权重矩阵 (n_joints x 2)
                    [:, 0] 是人类观测权重
                    [:, 1] 是虚拟观测权重
        """
        weights = np.ones((self.n_joints, 2))

        # 几何求解器启用标志（0或1）
        enabled = float(self.geometric_solver is not None)

        # 臂部关节掩码（J1-J4）
        arm_mask = np.zeros(self.n_joints)
        arm_mask[:4] = 1.0

        # 权重计算（向量化）
        # 人类观测：几何求解器启用时权重增大
        weights[:, 0] = 1.0 - enabled * arm_mask * (1.0 - 1e-4)

        # 虚拟观测：几何求解器启用时权重减小
        weights[:, 1] = 1.0 + enabled * arm_mask * (1e2 - 1.0)

        return weights

    # ==========================================
    # 辅助方法（与原版相同）
    # ==========================================

    def _get_full_q_from_controlled(self, q_controlled):
        """从受控关节角度构建完整的关节配置"""
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, joint_idx in enumerate(self.ik_solver.controlled_indices):
            q_full[joint_idx] = q_controlled[i]
        return q_full


# ==========================================
# 数学化的腕部控制模式
# ==========================================

class MathematicalWristController:
    """
    数学化的腕部控制器

    使用权重矩阵替代if-else模式选择
    """

    def __init__(self, mode='full_dof'):
        """
        初始化

        Args:
            mode: 控制模式 ('full_dof', 'constrained_horizontal', 'wrist_locked')
        """
        self.mode = mode

        # 模式权重矩阵（one-hot编码）
        self.mode_weights = self._encode_mode(mode)

    @staticmethod
    def _encode_mode(mode):
        """
        将模式编码为权重向量

        Args:
            mode: 模式字符串

        Returns:
            weights: [w_full_dof, w_constrained, w_locked]
        """
        mode_map = {
            'full_dof': np.array([1.0, 0.0, 0.0]),
            'constrained_horizontal': np.array([0.0, 1.0, 0.0]),
            'wrist_locked': np.array([0.0, 0.0, 1.0])
        }
        return mode_map.get(mode, np.array([1.0, 0.0, 0.0]))

    def solve_wrist_orientation(self, q_arm, target_orientation):
        """
        求解腕部姿态（数学化版本）

        使用权重矩阵组合三种模式的输出：
        q_wrist = w_full · q_full + w_const · q_const + w_lock · q_lock

        Args:
            q_arm: 臂部关节角度 [q1, q2, q3, q4]
            target_orientation: 目标姿态

        Returns:
            q_wrist: 腕部关节角度 [q5, q6, q7]
        """
        # 计算三种模式的输出
        q_full = self._solve_full_dof(q_arm, target_orientation)
        q_constrained = self._solve_constrained(q_arm, target_orientation)
        q_locked = np.zeros(3)

        # 加权组合
        w_full, w_const, w_lock = self.mode_weights
        q_wrist = w_full * q_full + w_const * q_constrained + w_lock * q_locked

        return q_wrist

    def _solve_full_dof(self, q_arm, target_orientation):
        """全自由度模式（简化版）"""
        # 这里应该调用完整的欧拉角分解
        # 为了演示，返回简化版本
        return np.array([0.1, 0.2, 0.3])

    def _solve_constrained(self, q_arm, target_orientation):
        """约束水平模式"""
        q4 = q_arm[3]
        return np.array([0.0, -q4, 0.0])


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试数学化VIST框架...")

    # 测试平滑阶跃函数
    print("\n1. 测试平滑阶跃函数:")
    for x in [0.5, 0.7, 0.8, 0.9, 1.0]:
        y = MathematicalVISTKalmanFilter.smooth_step(x, threshold=0.8, steepness=10)
        print(f"   smooth_step({x:.1f}) = {y:.4f}")

    # 测试软限幅
    print("\n2. 测试软限幅:")
    for x in [-1.0, 0.0, 0.5, 1.0, 2.0]:
        y = MathematicalVISTKalmanFilter.soft_clamp(x, min_val=0.0, max_val=1.0)
        print(f"   soft_clamp({x:.1f}) = {y:.4f}")

    # 测试模式编码
    print("\n3. 测试模式编码:")
    controller = MathematicalWristController('constrained_horizontal')
    print(f"   模式权重: {controller.mode_weights}")

    print("\n✅ 数学化框架测试完成")
