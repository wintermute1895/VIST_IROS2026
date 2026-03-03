#!/usr/bin/env python3
"""
VIST Kalman Filter - 完整论文框架实现

基于 IROS 论文的完整 VIST 算法：
v1.0: 基础恒速模型 + 固定噪声 ✅
v2.0: 意图检测 + 动态 Q/R 调度 + 过程噪声回拉 ✅
v3.0: 双观测源融合 + 位置距离融合意图检测 ✅
"""

import numpy as np
import time
import pinocchio as pin


class VISTKalmanFilter:
    """
    VIST 卡尔曼滤波器 - 完整论文框架 v3.0

    核心思想：
    通过统计约束（Q 和 R）而非几何约束实现流形导轨效果

    关键组件：
    1. 意图因子 α ∈ [0.05,0.95]：融合速度和位置距离
    2. 双观测源融合：z_human（遥操臂）+ z_virtual（IK到目标）
    3. 动态观测噪声：R_human(α) 随 α 增大而增大，R_virtual(α) 随 α 减小
    4. 过程噪声回拉：Q_joint = J† Σ_task (J†)^T
       - 任务空间各向异性约束（XY 小方差，Z 大方差）
       - 投影到关节空间产生非对称阻尼

    状态向量: x = [q, q̇]^T (14维)
    """

    def __init__(self, ik_solver, config, geometric_solver=None):
        """
        初始化 VIST 卡尔曼滤波器 v3.0（双观测源融合）

        Args:
            ik_solver: IK 求解器实例（用于雅可比计算和虚拟观测）
            config: 配置对象
            geometric_solver: 几何求解器（保留接口兼容性）
        """
        self.ik_solver = ik_solver
        self.config = config
        self.geometric_solver = geometric_solver

        # Pinocchio 模型（用于雅可比计算和前向运动学）
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
        self.R_human = self.R_base.copy()
        self.R_virtual = self.R_base.copy() * 0.1  # 虚拟观测噪声更小

        # ==========================================
        # VIST 核心参数 v3.0
        # ==========================================

        # 意图因子参数（扩大速度响应范围）
        self.velocity_threshold_low = 0.005   # m/s，精密对准阈值（降低）
        self.velocity_threshold_high = 0.15   # m/s，自由移动阈值（提高）

        # α的上下限（避免极端值）
        self.alpha_min = 0.05
        self.alpha_max = 0.95

        # 位置距离参数
        self.target_position_xy = np.array([0.41, -0.11])  # 目标孔位XY坐标
        self.distance_threshold_near = 0.01   # m，接近阈值
        self.distance_threshold_far = 0.10    # m，远离阈值

        # 意图因子融合权重
        self.velocity_weight = 0.6   # 速度权重
        self.distance_weight = 0.4   # 距离权重

        # 观测噪声调度参数
        self.r_scale_max = 100.0  # α=1 时 R_human 的放大倍数
        self.r_scale_min = 0.1    # α=0 时 R_virtual 的缩小倍数

        # 任务空间约束方差（Σ_task）
        self.sigma_task_xy = 0.0001  # XY 方向小方差（硬约束）
        self.sigma_task_z = 0.01     # Z 方向大方差（柔顺）

        # 雅可比伪逆阻尼系数
        self.jacobian_damping = 1e-4

        # 当前意图状态
        self.current_alpha = 0.5
        self.current_velocity_norm = 0.0
        self.current_distance_xy = 0.0
        self.is_precision_mode = False

        # 速度历史（用于平滑）
        self.velocity_history = []
        self.velocity_window_size = 5

        # 监控数据
        self.current_K = None  # 卡尔曼增益矩阵
        self.joint_delta = np.zeros(self.n_joints)  # 关节变化量
        self.last_joints = None  # 上一帧关节角度

        # 第一帧标志
        self._is_first_frame = True

        # 统计信息
        self.iteration_count = 0
        self.last_update_time = None

        print("✅ VIST卡尔曼滤波器初始化完成（v3.0 - 双观测源融合）")
        print(f"   - 状态维度: {self.state_dim} (7关节 × 2)")
        print(f"   - 时间步长: {self.dt}s ({1.0/self.dt:.1f}Hz)")
        print(f"   - 基础噪声: q_std={self.q_std_base}, r_std={self.r_std_base}")
        print(f"   - 速度阈值: 低={self.velocity_threshold_low} m/s, 高={self.velocity_threshold_high} m/s")
        print(f"   - α范围: [{self.alpha_min}, {self.alpha_max}]")
        print(f"   - 目标位置XY: {self.target_position_xy}")
        print(f"   - 距离阈值: 近={self.distance_threshold_near} m, 远={self.distance_threshold_far} m")
        print(f"   - 意图融合权重: 速度={self.velocity_weight}, 距离={self.distance_weight}")
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

    def _compute_end_effector_position(self, q_joints):
        """
        计算末端执行器的笛卡尔位置（前向运动学）

        Args:
            q_joints: 关节角度 (7,)

        Returns:
            ee_position: 末端位置 [x, y, z] (3,)
        """
        q_full = pin.neutral(self.model).copy()
        for i, ctrl_idx in enumerate(self.controlled_indices):
            q_full[ctrl_idx] = q_joints[i]

        pin.forwardKinematics(self.model, self.data, q_full)
        pin.updateFramePlacements(self.model, self.data)

        ee_pose = self.data.oMf[self.ee_frame_id]
        ee_position = ee_pose.translation

        return ee_position

    def _compute_damped_pseudoinverse(self, J):
        """计算阻尼最小二乘伪逆"""
        m, n = J.shape  # 3x7
        JJT = J @ J.T  # 3x3
        damping_matrix = self.jacobian_damping**2 * np.eye(m)
        J_pinv = J.T @ np.linalg.inv(JJT + damping_matrix)
        return J_pinv

    def _compute_intent_factor(self, cart_velocity_norm, ee_position):
        """
        计算意图因子 α ∈ [0.05, 0.95]（v3.0 改进版）

        融合两个因素：
        1. 速度因素：速度大 → 自由移动，速度小 → 精密对准
        2. 距离因素：距离远 → 自由移动，距离近 → 精密对准

        Args:
            cart_velocity_norm: 笛卡尔速度范数 (m/s)
            ee_position: 末端执行器位置 [x, y, z] (3,)

        Returns:
            alpha: 意图因子 [0.05, 0.95]
        """
        # 1. 速度因素 α_v ∈ [0, 1]
        if cart_velocity_norm >= self.velocity_threshold_high:
            alpha_v = 0.0
        elif cart_velocity_norm <= self.velocity_threshold_low:
            alpha_v = 1.0
        else:
            # 线性插值
            ratio = (cart_velocity_norm - self.velocity_threshold_low) / \
                    (self.velocity_threshold_high - self.velocity_threshold_low)
            alpha_v = 1.0 - ratio

        # 2. 距离因素 α_d ∈ [0, 1]
        # 计算末端到目标孔位的XY平面距离
        ee_xy = ee_position[:2]  # 只取XY坐标
        distance_xy = np.linalg.norm(ee_xy - self.target_position_xy)
        self.current_distance_xy = distance_xy

        if distance_xy >= self.distance_threshold_far:
            alpha_d = 0.0  # 距离远，自由移动
        elif distance_xy <= self.distance_threshold_near:
            alpha_d = 1.0  # 距离近，精密对准
        else:
            # 线性插值
            ratio = (distance_xy - self.distance_threshold_near) / \
                    (self.distance_threshold_far - self.distance_threshold_near)
            alpha_d = 1.0 - ratio

        # 3. 融合两个因素（加权平均）
        alpha_raw = self.velocity_weight * alpha_v + self.distance_weight * alpha_d

        # 4. 限制在 [alpha_min, alpha_max] 范围内（避免极端值）
        alpha = np.clip(alpha_raw, self.alpha_min, self.alpha_max)

        # 5. 更新精密模式标志
        self.is_precision_mode = (alpha > 0.5)

        return alpha

    def _update_observation_noise(self, alpha):
        """
        动态观测噪声整形：R_human(α) 和 R_virtual(α)（v3.0 双观测源）

        论文公式：
        - R_human 随 α 增大而指数级增加（精密阶段屏蔽人手抖动）
        - R_virtual 随 α 增大而减小（精密阶段更信任虚拟引导）

        Args:
            alpha: 意图因子 [0.05, 0.95]
        """
        # R_human: α越大，噪声越大（不信任人类输入）
        scale_factor_human = 1.0 + (self.r_scale_max - 1.0) * (alpha ** 2)
        self.R_human = self.R_base * scale_factor_human

        # R_virtual: α越大，噪声越小（更信任虚拟引导）
        scale_factor_virtual = 1.0 - (1.0 - self.r_scale_min) * (alpha ** 2)
        self.R_virtual = self.R_base * scale_factor_virtual

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
        VIST 卡尔曼滤波器主更新函数 v3.0（双观测源融合）

        核心思想：通过动态调整 Q 和 R 实现流形约束

        算法流程：
        1. 卡尔曼预测 → 估计关节速度
        2. 雅可比正向映射 → 笛卡尔速度和位置
        3. 计算意图因子 α（融合速度和位置距离）
        4. 动态调整观测噪声 R_human(α) 和 R_virtual(α)
        5. 过程噪声回拉 Q = J† Σ_task (J†)^T
        6. 双观测源融合更新（如果有虚拟观测）

        Args:
            shadow_joints: 观测关节角度（来自遥操臂）
            target_pose: 目标末端位姿（用于生成虚拟观测）
            virtual_joints: 虚拟引导关节角度（可选，如果提供则进行双观测融合）

        Returns:
            filtered_joints: 滤波后的关节角度
        """
        self.iteration_count += 1
        z_human = np.array(shadow_joints)

        # 第一帧：初始化
        if self._is_first_frame:
            print(f"[VIST v3.0] 第一帧同步")
            print(f"  观测值: {z_human}")
            self.state[:self.n_joints] = z_human.copy()
            self.state[self.n_joints:] = 0.0
            self.last_joints = z_human.copy()
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
        # 步骤2: 计算雅可比、笛卡尔速度和末端位置
        # ==========================================
        J_pos = self._compute_jacobian(q_pred)
        cart_velocity = J_pos @ q_dot_pred
        ee_position = self._compute_end_effector_position(q_pred)

        # ==========================================
        # 步骤3: 计算意图因子 α（融合速度和位置距离）
        # ==========================================
        cart_velocity_norm = np.linalg.norm(cart_velocity)

        # 速度历史平滑
        self.velocity_history.append(cart_velocity_norm)
        if len(self.velocity_history) > self.velocity_window_size:
            self.velocity_history.pop(0)
        cart_velocity_norm_smoothed = np.mean(self.velocity_history)

        alpha = self._compute_intent_factor(cart_velocity_norm_smoothed, ee_position)
        self.current_alpha = alpha
        self.current_velocity_norm = cart_velocity_norm_smoothed

        # ==========================================
        # 步骤4: 动态调整观测噪声 R_human(α) 和 R_virtual(α)
        # ==========================================
        self._update_observation_noise(alpha)

        # ==========================================
        # 步骤5: 过程噪声回拉 Q = J† Σ_task (J†)^T
        # ==========================================
        Q_joint_velocity = self._pullback_process_noise(alpha, J_pos)
        self.Q = self._construct_full_Q(Q_joint_velocity)

        # ==========================================
        # 步骤6: 双观测源融合更新
        # ==========================================
        if virtual_joints is not None:
            # 双观测源融合（顺序更新）
            z_virtual = np.array(virtual_joints)

            # 6.1 人类观测更新
            innovation_human = z_human - self.H @ x_pred
            S_human = self.H @ P_pred @ self.H.T + self.R_human
            K_human = P_pred @ self.H.T @ np.linalg.inv(S_human)

            x_after_human = x_pred + K_human @ innovation_human
            I = np.eye(self.state_dim)
            P_after_human = (I - K_human @ self.H) @ P_pred

            # 6.2 虚拟观测更新
            innovation_virtual = z_virtual - self.H @ x_after_human
            S_virtual = self.H @ P_after_human @ self.H.T + self.R_virtual
            K_virtual = P_after_human @ self.H.T @ np.linalg.inv(S_virtual)

            self.state = x_after_human + K_virtual @ innovation_virtual
            self.P = (I - K_virtual @ self.H) @ P_after_human

            # 保存增益矩阵（用于监控）
            self.current_K = K_virtual  # 保存最后一个增益

        else:
            # 单观测源更新（仅人类观测）
            innovation = z_human - self.H @ x_pred
            S = self.H @ P_pred @ self.H.T + self.R_human
            K = P_pred @ self.H.T @ np.linalg.inv(S)

            self.state = x_pred + K @ innovation
            I = np.eye(self.state_dim)
            self.P = (I - K @ self.H) @ P_pred

            # 保存增益矩阵（用于监控）
            self.current_K = K

        filtered_joints = self.state[:self.n_joints].copy()

        # 计算关节变化量
        if self.last_joints is not None:
            self.joint_delta = filtered_joints - self.last_joints
        self.last_joints = filtered_joints.copy()

        # 每100帧打印统计信息
        if self.iteration_count % 100 == 0:
            print(f"\n[VIST v3.0 双观测融合] 第{self.iteration_count}帧统计:")
            print(f"  人类观测: {z_human[:3]}... (前3个关节)")
            if virtual_joints is not None:
                print(f"  虚拟观测: {z_virtual[:3]}... (前3个关节)")
            print(f"  滤波值: {filtered_joints[:3]}... (前3个关节)")
            print(f"  末端位置XY: [{ee_position[0]:.4f}, {ee_position[1]:.4f}]")
            print(f"  目标位置XY: {self.target_position_xy}")
            print(f"  XY距离: {self.current_distance_xy:.4f} m")
            print(f"  笛卡尔速度: {cart_velocity} m/s")
            print(f"  速度范数: {cart_velocity_norm:.4f} m/s (平滑: {cart_velocity_norm_smoothed:.4f})")
            print(f"  意图因子 α: {alpha:.3f} ({'精密对准' if self.is_precision_mode else '自由移动'})")
            print(f"  R_human 放大: {np.trace(self.R_human) / np.trace(self.R_base):.2f}x")
            print(f"  R_virtual 缩小: {np.trace(self.R_virtual) / np.trace(self.R_base):.2f}x")
            print(f"  Q 速度方差: {np.trace(Q_joint_velocity):.6f}")
            print(f"  关节变化量范数: {np.linalg.norm(self.joint_delta):.6f}\n")

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

    def get_kalman_gain(self):
        """获取卡尔曼增益矩阵 K（用于监控）"""
        return self.current_K

    def get_joint_delta(self):
        """获取关节变化量（用于监控）"""
        return self.joint_delta

    def get_distance_to_target(self):
        """获取末端到目标的XY距离（用于监控）"""
        return self.current_distance_xy
