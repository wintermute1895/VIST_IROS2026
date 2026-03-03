#!/usr/bin/env python3
"""
VIST Kalman Filter - 完整论文框架实现

基于 IROS 论文的完整 VIST 算法：
v1.0: 基础恒速模型 + 固定噪声 ✅
v2.0: 意图检测 + 动态 Q/R 调度 + 过程噪声回拉 ✅
v3.0: 双观测源融合（待开发）
"""

import numpy as np
import time
import pinocchio as pin


class VISTKalmanFilter:
    """
    VIST 卡尔曼滤波器 - 完整论文框架 v2.0

    核心思想：
    通过统计约束（Q 和 R）而非几何约束实现流形导轨效果

    关键组件：
    1. 意图因子 α ∈ [0,1]：基于速度范数（简化版）
    2. 动态观测噪声：R_human(α) 随 α 增大而增大
    3. 过程噪声回拉：Q_joint = J† Σ_task (J†)^T
       - 任务空间各向异性约束（XY 小方差，Z 大方差）
       - 投影到关节空间产生非对称阻尼

    状态向量: x = [q, q̇]^T (14维)
    """

    def __init__(self, ik_solver, config, geometric_solver=None):
        """
        初始化 VIST 卡尔曼滤波器 v2.0（完整论文框架）

        Args:
            ik_solver: IK 求解器实例（用于雅可比计算）
            config: 配置对象
            geometric_solver: 几何求解器（保留接口兼容性）
        """
        self.ik_solver = ik_solver
        self.config = config
        self.geometric_solver = geometric_solver

        # Pinocchio 模型（用于雅可比计算）
        self.model = ik_solver.model
        self.data = ik_solver.data
        self.ee_frame_id = ik_solver.ee_frame_id
        self.controlled_indices = ik_solver.controlled_indices

        # 状态空间维度
        self.n_joints = 7
        self.state_dim = 14  # 2 * n_joints

        # 时间步长
        self.dt = 0.0125  # 80Hz

        # 初始化状态向量和协方差
        self.state = np.zeros(self.state_dim)
        self.P = np.eye(self.state_dim)
        self.P[:self.n_joints, :self.n_joints] *= 0.01
        self.P[self.n_joints:, self.n_joints:] *= 0.1

        # 构建状态转移矩阵 F（恒速模型）
        self.F = np.eye(self.state_dim)
        self.F[:self.n_joints, self.n_joints:] = self.dt * np.eye(self.n_joints)

        # 构建观测矩阵 H（只观测位置）
        self.H = np.zeros((self.n_joints, self.state_dim))
        self.H[:self.n_joints, :self.n_joints] = np.eye(self.n_joints)

        # ==========================================
        # 基础噪声协方差（α=0 时的值）
        # ==========================================
        self.q_std_base = 0.01  # 基础过程噪声
        self.r_std_base = 0.05  # 基础观测噪声

        # 基础 Q 矩阵（恒速模型）
        Q_vel = self.q_std_base**2 * np.eye(self.n_joints)
        self.Q_base = np.zeros((self.state_dim, self.state_dim))
        self.Q_base[:self.n_joints, :self.n_joints] = (self.dt**3 / 3.0) * Q_vel
        self.Q_base[:self.n_joints, self.n_joints:] = (self.dt**2 / 2.0) * Q_vel
        self.Q_base[self.n_joints:, :self.n_joints] = (self.dt**2 / 2.0) * Q_vel
        self.Q_base[self.n_joints:, self.n_joints:] = self.dt * Q_vel

        # 基础 R 矩阵
        self.R_base = (self.r_std_base**2) * np.eye(self.n_joints)

        # 当前使用的 Q 和 R（会动态更新）
        self.Q = self.Q_base.copy()
        self.R = self.R_base.copy()

        # ==========================================
        # VIST 核心参数
        # ==========================================

        # 意图因子参数
        self.velocity_threshold_low = 0.01   # m/s，精密对准阈值
        self.velocity_threshold_high = 0.05  # m/s，自由移动阈值

        # 观测噪声调度参数
        self.r_scale_max = 100.0  # α=1 时 R_human 的放大倍数

        # 任务空间约束方差（Σ_task）
        self.sigma_task_xy = 0.0001  # XY 方向小方差（硬约束）
        self.sigma_task_z = 0.01     # Z 方向大方差（柔顺）

        # 雅可比伪逆阻尼系数
        self.jacobian_damping = 1e-4

        # 当前意图状态
        self.current_alpha = 0.0
        self.current_velocity_norm = 0.0
        self.is_precision_mode = False

        # 速度历史（用于平滑）
        self.velocity_history = []
        self.velocity_window_size = 5

        # 第一帧标志
        self._is_first_frame = True

        # 统计信息
        self.iteration_count = 0
        self.last_update_time = None

        print("✅ VIST卡尔曼滤波器初始化完成（v2.0 - 完整论文框架）")
        print(f"   - 状态维度: {self.state_dim} (7关节 × 2)")
        print(f"   - 时间步长: {self.dt}s ({1.0/self.dt:.1f}Hz)")
        print(f"   - 基础噪声: q_std={self.q_std_base}, r_std={self.r_std_base}")
        print(f"   - 速度阈值: 低={self.velocity_threshold_low} m/s, 高={self.velocity_threshold_high} m/s")
        print(f"   - R 放大倍数: {self.r_scale_max}x (α=1 时)")
        print(f"   - 任务空间约束: σ_xy={self.sigma_task_xy}, σ_z={self.sigma_task_z}")
        print(f"   - 雅可比阻尼: λ={self.jacobian_damping}")

    def _compute_jacobian(self, q_joints):
        """计算末端执行器的雅可比矩阵"""
        q_full = pin.neutral(self.model).copy()
        for i, ctrl_idx in enumerate(self.controlled_indices):
            q_full[ctrl_idx] = q_joints[i]

        pin.forwardKinematics(self.model, self.data, q_full)
        pin.updateFramePlacements(self.model, self.data)

        J_full = pin.computeFrameJacobian(
            self.model, self.data, q_full, self.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        J = J_full[:, self.controlled_indices]  # 6x7
        J_pos = J[:3, :]  # 3x7 (只有位置)

        return J_pos

    def _compute_damped_pseudoinverse(self, J):
        """计算阻尼最小二乘伪逆"""
        m, n = J.shape  # 3x7
        JJT = J @ J.T  # 3x3
        damping_matrix = self.jacobian_damping**2 * np.eye(m)
        J_pinv = J.T @ np.linalg.inv(JJT + damping_matrix)
        return J_pinv

    def _compute_intent_factor(self, cart_velocity_norm):
        """
        计算意图因子 α ∈ [0, 1]

        基于速度范数的简化版本：
        - 速度大 → α=0（自由移动）
        - 速度小 → α=1（精密对准）

        Args:
            cart_velocity_norm: 笛卡尔速度范数 (m/s)

        Returns:
            alpha: 意图因子 [0, 1]
        """
        if cart_velocity_norm >= self.velocity_threshold_high:
            alpha = 0.0
            self.is_precision_mode = False
        elif cart_velocity_norm <= self.velocity_threshold_low:
            alpha = 1.0
            self.is_precision_mode = True
        else:
            # 线性插值
            ratio = (cart_velocity_norm - self.velocity_threshold_low) / \
                    (self.velocity_threshold_high - self.velocity_threshold_low)
            alpha = 1.0 - ratio
            self.is_precision_mode = (alpha > 0.5)

        return alpha

    def _update_observation_noise(self, alpha):
        """
        动态观测噪声整形：R_human(α)

        论文公式：R_human 随 α 增大而指数级增加
        目的：在精密阶段屏蔽人手抖动

        Args:
            alpha: 意图因子 [0, 1]
        """
        # 指数增长：R = R_base * (1 + (scale_max - 1) * α²)
        scale_factor = 1.0 + (self.r_scale_max - 1.0) * (alpha ** 2)
        self.R = self.R_base * scale_factor

    def _pullback_process_noise(self, alpha, J_pos):
        """
        过程噪声协方差回拉（VIST 的灵魂）

        论文公式：Q_joint = J† Σ_task (J†)^T

        物理意义：
        - 任务空间各向异性约束（XY 小方差，Z 大方差）
        - 投影到关节空间产生非对称阻尼
        - 横向硬约束，进给方向柔顺

        Args:
            alpha: 意图因子 [0, 1]
            J_pos: 位置雅可比矩阵 (3x7)

        Returns:
            Q_pullback: 回拉后的过程噪声协方差 (7x7，速度部分)
        """
        # 任务空间约束方差矩阵 Σ_task (3x3)
        # α=0 时无约束，α=1 时强约束
        sigma_xy = self.sigma_task_xy + (1.0 - alpha) * 0.01  # XY 方向
        sigma_z = self.sigma_task_z  # Z 方向保持柔顺

        Sigma_task = np.diag([sigma_xy, sigma_xy, sigma_z])

        # 计算雅可比伪逆
        J_pinv = self._compute_damped_pseudoinverse(J_pos)  # 7x3

        # 回拉映射：Q_joint = J† Σ_task (J†)^T
        Q_pullback = J_pinv @ Sigma_task @ J_pinv.T  # 7x7

        return Q_pullback

    def _construct_full_Q(self, Q_joint_velocity):
        """
        构建完整的 Q 矩阵 (14x14)

        Args:
            Q_joint_velocity: 关节速度部分的协方差 (7x7)

        Returns:
            Q_full: 完整的过程噪声协方差 (14x14)
        """
        Q_full = np.zeros((self.state_dim, self.state_dim))

        # 使用离散化恒速模型的噪声传播
        Q_full[:self.n_joints, :self.n_joints] = (self.dt**3 / 3.0) * Q_joint_velocity
        Q_full[:self.n_joints, self.n_joints:] = (self.dt**2 / 2.0) * Q_joint_velocity
        Q_full[self.n_joints:, :self.n_joints] = (self.dt**2 / 2.0) * Q_joint_velocity
        Q_full[self.n_joints:, self.n_joints:] = self.dt * Q_joint_velocity

        return Q_full

    def update(self, shadow_joints, target_pose, virtual_joints=None):
        """
        VIST 卡尔曼滤波器主更新函数 v2.0（完整论文框架）

        核心思想：通过动态调整 Q 和 R 实现流形约束

        算法流程：
        1. 卡尔曼预测 → 估计关节速度
        2. 雅可比正向映射 → 笛卡尔速度
        3. 计算意图因子 α（基于速度）
        4. 动态调整观测噪声 R(α)
        5. 过程噪声回拉 Q = J† Σ_task (J†)^T
        6. 卡尔曼更新（使用动态 Q 和 R）

        Args:
            shadow_joints: 观测关节角度（来自遥操臂）
            target_pose: 目标末端位姿（保留接口兼容性）
            virtual_joints: 虚拟引导关节角度（保留接口兼容性）

        Returns:
            filtered_joints: 滤波后的关节角度
        """
        self.iteration_count += 1
        z = np.array(shadow_joints)

        # 第一帧：初始化
        if self._is_first_frame:
            print(f"[VIST v2.0] 第一帧同步")
            print(f"  观测值: {z}")
            self.state[:self.n_joints] = z.copy()
            self.state[self.n_joints:] = 0.0
            self._is_first_frame = False
            print(f"  初始化完成\n")

        # 动态更新时间步长
        current_time = time.time()
        if self.last_update_time is not None:
            actual_dt = current_time - self.last_update_time
            if 0.001 < actual_dt < 0.1:
                self.F[:self.n_joints, self.n_joints:] = actual_dt * np.eye(self.n_joints)
        self.last_update_time = current_time

        # ==========================================
        # 步骤1: 卡尔曼预测（使用当前的 Q）
        # ==========================================
        x_pred = self.F @ self.state
        P_pred = self.F @ self.P @ self.F.T + self.Q

        q_pred = x_pred[:self.n_joints]
        q_dot_pred = x_pred[self.n_joints:]

        # ==========================================
        # 步骤2: 计算雅可比和笛卡尔速度
        # ==========================================
        J_pos = self._compute_jacobian(q_pred)
        cart_velocity = J_pos @ q_dot_pred

        # ==========================================
        # 步骤3: 计算意图因子 α
        # ==========================================
        cart_velocity_norm = np.linalg.norm(cart_velocity)

        # 速度历史平滑
        self.velocity_history.append(cart_velocity_norm)
        if len(self.velocity_history) > self.velocity_window_size:
            self.velocity_history.pop(0)
        cart_velocity_norm_smoothed = np.mean(self.velocity_history)

        alpha = self._compute_intent_factor(cart_velocity_norm_smoothed)
        self.current_alpha = alpha
        self.current_velocity_norm = cart_velocity_norm_smoothed

        # ==========================================
        # 步骤4: 动态调整观测噪声 R(α)
        # ==========================================
        self._update_observation_noise(alpha)

        # ==========================================
        # 步骤5: 过程噪声回拉 Q = J† Σ_task (J†)^T
        # ==========================================
        Q_joint_velocity = self._pullback_process_noise(alpha, J_pos)
        self.Q = self._construct_full_Q(Q_joint_velocity)

        # ==========================================
        # 步骤6: 卡尔曼更新（使用动态 Q 和 R）
        # ==========================================
        innovation = z - self.H @ x_pred
        S = self.H @ P_pred @ self.H.T + self.R
        K = P_pred @ self.H.T @ np.linalg.inv(S)

        self.state = x_pred + K @ innovation
        I = np.eye(self.state_dim)
        self.P = (I - K @ self.H) @ P_pred

        filtered_joints = self.state[:self.n_joints].copy()

        # 每100帧打印统计信息
        if self.iteration_count % 100 == 0:
            print(f"\n[VIST v2.0 论文框架] 第{self.iteration_count}帧统计:")
            print(f"  观测值: {z[:3]}... (前3个关节)")
            print(f"  滤波值: {filtered_joints[:3]}... (前3个关节)")
            print(f"  笛卡尔速度: {cart_velocity} m/s")
            print(f"  速度范数: {cart_velocity_norm:.4f} m/s (平滑: {cart_velocity_norm_smoothed:.4f})")
            print(f"  意图因子 α: {alpha:.3f} ({'精密对准' if self.is_precision_mode else '自由移动'})")
            print(f"  R 放大倍数: {np.trace(self.R) / np.trace(self.R_base):.2f}x")
            print(f"  Q 速度方差: {np.trace(Q_joint_velocity):.6f}")
            print(f"  创新范数: {np.linalg.norm(innovation):.6f}\n")

        return filtered_joints

    def reset(self, initial_joints=None):
        """重置滤波器状态"""
        if initial_joints is not None:
            self.state[:self.n_joints] = initial_joints
        else:
            self.state = np.zeros(self.state_dim)

        self.P = np.eye(self.state_dim)
        self.P[:self.n_joints, :self.n_joints] *= 0.01
        self.P[self.n_joints:, self.n_joints:] *= 0.1

        self._is_first_frame = True
        print("✅ VIST卡尔曼滤波器已重置")

    def get_velocity_estimate(self):
        """获取速度估计"""
        return self.state[self.n_joints:]

    def get_intent_factor(self):
        """获取意图因子 α"""
        return self.current_alpha
