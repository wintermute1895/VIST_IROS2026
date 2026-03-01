#!/usr/bin/env python3
"""
VIST Kalman Filter - 基于意图感知的遥操作统一状态估计框架

核心功能：
1. 卡尔曼滤波状态估计（关节空间）
2. 微分 IK 观测模型
3. 意图驱动的协方差调度
4. 各向异性过程噪声（肘部约束）

参考文档：docs/VIST_modeling.md
"""

import numpy as np
import pinocchio as pin
from scipy.linalg import inv
from src.utils.lie_algebra import slerp_rotation
from src.utils.parameter_override import ParameterOverrideManager


class VISTKalmanFilter:
    """
    VIST 卡尔曼滤波器

    状态向量: x = [θ, θ̇]^T  (14维)
    - θ: 7个关节角度
    - θ̇: 7个关节速度

    过程模型: x(k+1) = F·x(k) + w(k)
    - F: 恒速模型状态转移矩阵
    - w: 各向异性过程噪声（肘部方差更小）

    观测模型: z = H·x + v
    - z: [Δθ_human, Δθ_virtual]^T
    - Δθ_human: 人类指令（直接映射）
    - Δθ_virtual: 虚拟引导（微分 IK）
    - v: 意图驱动的观测噪声
    """

    def __init__(self, ik_solver, config, geometric_solver=None):
        """
        初始化 VIST 卡尔曼滤波器

        Args:
            ik_solver: IK 求解器实例（用于微分 IK）
            config: 配置对象
            geometric_solver: 几何解析求解器（可选，用于肘部约束）
        """
        self.ik_solver = ik_solver
        self.config = config
        self.geometric_solver = geometric_solver

        # 参数覆盖管理器
        self.override_manager = ParameterOverrideManager()

        # 状态空间维度
        self.n_joints = config.vist_n_joints
        self.state_dim = config.vist_state_dim  # 2 * n_joints

        # 时间步长
        self.dt = config.vist_process_dt

        # ==========================================
        # 1. 初始化状态向量和协方差
        # ==========================================
        self.state = np.zeros(self.state_dim)  # [θ, θ̇]
        self.P = np.eye(self.state_dim)  # 状态协方差矩阵

        # 初始化协方差
        self.P[:self.n_joints, :self.n_joints] *= config.vist_initial_state_variance
        self.P[self.n_joints:, self.n_joints:] *= config.vist_initial_velocity_variance

        # ==========================================
        # 2. 意图检测状态（必须在构建Q矩阵之前初始化）
        # ==========================================
        self.alpha = 0.0  # 意图因子 (0=自由移动, 1=精密操作)
        self.alpha_smoothed = 0.0  # 平滑后的意图因子

        # ==========================================
        # 3. 构建状态转移矩阵 F（恒速模型）
        # ==========================================
        # F = [I  dt*I]
        #     [0   I  ]
        self.F = np.eye(self.state_dim)
        self.F[:self.n_joints, self.n_joints:] = self.dt * np.eye(self.n_joints)

        # ==========================================
        # 4. 构建过程噪声协方差 Q（各向异性）
        # ==========================================
        self.Q = self._build_process_noise_covariance()

        # ==========================================
        # 5. 构建观测矩阵 H
        # ==========================================
        # 观测向量 z = [q_human, q_virtual]^T (14维)
        # 注意：观测是目标关节角度（绝对值），不是增量
        #
        # H = [I  0]  (人类指令：直接观测关节位置)
        #     [I  0]  (虚拟引导：已通过微分IK转换到关节空间)
        #
        # Note: 虚拟引导的流形投影(Jacobian)已在外部的 Differential IK 中隐式完成，
        # 转换为关节空间目标。此处保持恒等映射(Identity Matrix)是为了避免 EKF
        # 在奇异点处的数值求逆爆炸，确保 50Hz 控制的绝对安全。
        self.H = np.zeros((2 * self.n_joints, self.state_dim))
        self.H[:self.n_joints, :self.n_joints] = np.eye(self.n_joints)
        self.H[self.n_joints:, :self.n_joints] = np.eye(self.n_joints)

        # ==========================================
        # 6. 历史数据（用于计算人类指令增量）
        # ==========================================
        self.previous_target_pos = None  # 上一帧目标位置

        # 【修复】移除预滤波器相关变量
        # 所有滤波工作由卡尔曼滤波器的协方差调度完成

        # ==========================================
        # 7. 统计信息
        # ==========================================
        self.iteration_count = 0

    def _build_process_noise_covariance(self):
        """
        构建过程噪声协方差矩阵 Q（含任务空间流形约束）

        【核心创新】任务空间流形约束通过雅可比投影：
        在精密插入阶段（α > 0.8），通过任务空间约束自动协调各关节配合。

        理论框架：
        1. 在任务空间定义约束流形 M ⊂ SE(3)
           - 垂直插入：只允许Z方向运动，其他5-DOF固定
           - Σ_task = diag([ε, ε, σ_z², ε, ε, ε])

        2. 通过雅可比伪逆投影到关节空间
           - Q_cons = J† Σ_task (J†)^T
           - 自动计算各关节需要的协方差配合

        3. 与意图因子α融合
           - Q(α) = (1-α)Q_free + αQ_cons
           - 平滑过渡，无硬切换

        优势：
        - 腕部关节不会被锁死，而是自动配合大臂运动
        - 保持末端姿态不变（水平插入）
        - 纯数学解决方案，无工程补丁

        Returns:
            Q: 过程噪声协方差矩阵 (state_dim x state_dim)
        """
        Q = np.zeros((self.state_dim, self.state_dim))

        # ==========================================
        # 第一步：构建基础协方差 Q_free（自由运动）
        # ==========================================
        Q_free = self._build_base_process_noise()

        # ==========================================
        # 第二步：判断是否需要应用流形约束
        # ==========================================
        # 获取参数覆盖
        override = self.override_manager.get_override()

        # 应用阈值覆盖
        z_lock_threshold = override.z_lock_threshold_override if override.z_lock_threshold_override is not None else 0.8

        # 检查是否应用流形约束
        should_apply_manifold = override.should_apply_manifold(self.alpha_smoothed, z_lock_threshold)

        if not should_apply_manifold:
            # 粗略阶段：使用自由协方差
            Q_final = override.get_q_matrix(Q_free)
            return Q_final

        # ==========================================
        # 第三步：应用任务空间流形约束
        # ==========================================
        try:
            # 1. 获取当前关节配置
            q_controlled = self.state[:self.n_joints]
            q_full = self._get_full_q_from_controlled(q_controlled)

            if not np.all(np.isfinite(q_full)):
                Q_final = override.get_q_matrix(Q_free)
                return Q_final

            # 2. 计算完整雅可比矩阵（6×n_joints：位置+姿态）
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

            J_full = pin.computeFrameJacobian(
                self.ik_solver.model,
                self.ik_solver.data,
                q_full,
                self.ik_solver.ee_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )  # 6×7 矩阵

            # 只使用受控关节
            J = J_full[:, self.ik_solver.controlled_indices]  # 6×n_joints

            # 3. 定义任务空间约束协方差
            # 垂直插入流形：只允许Z方向运动，其他5个自由度强约束
            eps = 1e-4  # 强约束（极小方差）
            sigma_z = 1.0  # 弱约束（允许Z方向运动）

            # Σ_task = diag([ε, ε, σ_z², ε, ε, ε])
            # 顺序：[x, y, z, rx, ry, rz]
            Sigma_task_cons = np.diag([eps, eps, sigma_z, eps, eps, eps])

            # 4. 通过雅可比伪逆投影到关节空间
            # Q_cons = J† Σ_task (J†)^T
            # 使用阻尼伪逆避免奇异性
            damping = 1e-3
            J_pinv = J.T @ np.linalg.inv(J @ J.T + damping * np.eye(6))

            # 投影到关节空间（位置部分）
            Q_cons_position = J_pinv @ Sigma_task_cons @ J_pinv.T  # n_joints × n_joints

            # 5. 扩展到完整状态空间（位置+速度）
            # 按照论文公式构建完整的2n×2n协方差矩阵，包含交叉项：
            # Q = [Δt³/3·Σ_vel   Δt²/2·Σ_vel]
            #     [Δt²/2·Σ_vel   Δt·Σ_vel  ]
            Q_cons = np.zeros((self.state_dim, self.state_dim))

            # 位置-位置块 (左上)
            Q_cons[:self.n_joints, :self.n_joints] = (self.dt**3 / 3.0) * Q_cons_position

            # 位置-速度块 (右上)
            Q_cons[:self.n_joints, self.n_joints:] = (self.dt**2 / 2.0) * Q_cons_position

            # 速度-位置块 (左下，对称)
            Q_cons[self.n_joints:, :self.n_joints] = (self.dt**2 / 2.0) * Q_cons_position

            # 速度-速度块 (右下)
            Q_cons[self.n_joints:, self.n_joints:] = self.dt * Q_cons_position

            # 6. 根据意图因子α插值融合
            # α = 0.8 → blend_factor = 0（自由运动）
            # α = 1.0 → blend_factor = 1（完全约束）
            blend_factor = (self.alpha_smoothed - z_lock_threshold) / (1.0 - z_lock_threshold)
            blend_factor = np.clip(blend_factor, 0.0, 1.0)

            # Q(α) = (1-α)Q_free + αQ_cons
            Q_final = (1 - blend_factor) * Q_free + blend_factor * Q_cons

            # 应用Q矩阵覆盖
            Q_final = override.get_q_matrix(Q_final)

            return Q_final

        except Exception as e:
            # 流形约束投影失败，回退到自由协方差
            print(f"⚠️ [VIST] 任务空间流形约束投影失败: {e}")
            import traceback
            traceback.print_exc()
            Q_final = override.get_q_matrix(Q_free)
            return Q_final

    def _build_base_process_noise(self):
        """
        构建基础过程噪声协方差（自由运动）

        关节特定调优：
        - J1 (肩俯仰): 3.0× 增强（前向运动）
        - J2 (肩侧摆): 2.0× 增强
        - J3 (肩旋转): 0.1× 阻尼（冗余自由度强阻尼）
        - J4 (肘关节): 1.2× 增强（任务关节）
        - J5-J7 (腕部): 1.0× 标准

        Returns:
            Q_free: 基础过程噪声协方差矩阵 (state_dim x state_dim)
        """
        Q = np.zeros((self.state_dim, self.state_dim))

        # 位置部分（关节角度）
        pos_variance = self.config.vist_position_variance
        Q[:self.n_joints, :self.n_joints] = pos_variance * np.eye(self.n_joints)

        # 速度部分（关节速度）
        vel_variance = self.config.vist_velocity_variance
        Q[self.n_joints:, self.n_joints:] = vel_variance * np.eye(self.n_joints)

        # 关节特定调优
        joint_scales = {
            0: 3.0,  # J1 (肩俯仰): 前向运动关键关节
            1: 2.0,  # J2 (肩侧摆): 适度增强
            2: 0.1,  # J3 (肩旋转): 冗余DOF强阻尼
            3: 1.2,  # J4 (肘关节): 任务关节
            4: 1.0,  # J5 (腕俯仰): 标准
            5: 1.0,  # J6 (腕侧摆): 标准
            6: 1.0,  # J7 (腕旋转): 标准
        }

        for i in range(self.n_joints):
            scale = joint_scales.get(i, 1.0)
            Q[i, i] *= scale
            Q[self.n_joints + i, self.n_joints + i] *= scale

        return Q

    def _build_observation_noise_covariance(self, use_biomimetic=False,
                                           human_delta_theta=None,
                                           virtual_delta_theta=None):
        """
        构建意图驱动的观测噪声协方差矩阵 R（含冲突检测）

        R = [R_human    0      ]
            [0       R_virtual]

        - R_human: 人类指令噪声（α → 0 时增大，强力去噪）
        - R_virtual: 虚拟引导噪声（α → 1 时减小，磁吸引导）

        【核心创新】挣脱机制（R_conflict）：
        当操作员检测到算法引导错误时，会主动施加与虚拟引导相反的力，
        此时 ||Δθ_human - Δθ_virtual|| 增大。

        我们通过动态调整虚拟引导的观测噪声来实现"挣脱"：
        R_virtual(α, conflict) = R_base(α) + γ_c · ||Δθ_human - Δθ_virtual||²

        当冲突增大时，R_virtual 增大，卡尔曼增益 K 会自动降低虚拟引导的权重，
        允许操作员"挣脱"错误的引导进行微调。

        【关键修正】：在仿生观测模式下，J4 的观测来自直接的几何测量（肘部角度），
        应该和手部位置一样可信，因此大幅降低其观测噪声。

        Args:
            use_biomimetic: 是否使用仿生观测模型
            human_delta_theta: 人类指令增量（用于冲突检测）
            virtual_delta_theta: 虚拟引导增量（用于冲突检测）

        Returns:
            R: 观测噪声协方差矩阵 (2*n_joints x 2*n_joints)
        """
        R = np.zeros((2 * self.n_joints, 2 * self.n_joints))

        # ==========================================
        # 1. 人类指令噪声（意图驱动 - 论文3.0版本：指数形式）
        # ==========================================
        # 论文公式：R_human(α) = R_base × exp(λα) × I
        #
        # 物理含义：
        # - α → 0 (自由移动): R_human ≈ R_base，保持基础滤波
        # - α → 1 (精密操作): R_human = R_base × exp(λ)，指数级增大噪声，强力抑制人类抖动
        #
        # 优势：指数增长提供更陡峭的"去颤"效果

        lambda_h = self.config.vist_human_lambda if hasattr(self.config, 'vist_human_lambda') else 3.0
        R_base_human = self.config.vist_human_base_variance

        # 【修复】始终使用意图驱动的指数形式，保持论文核心机制
        # 即使在几何求解器模式下，也应该通过α因子动态调整去颤强度
        # 而不是硬编码固定值
        human_variance = R_base_human * np.exp(lambda_h * self.alpha_smoothed)

        R[:self.n_joints, :self.n_joints] = human_variance * np.eye(self.n_joints)

        # 【关键修正】在仿生观测模式下，J4 的观测是高置信度的几何测量
        # 但仍需要适当的滤波来处理原始数据的抖动
        if use_biomimetic:
            elbow_idx = 3  # J4 = 索引3
            # J4 的观测方差：平衡响应性和平滑性
            # 1e-4 太小（不滤波，抖动大）
            # 1e-2 太大（响应慢）
            # 5e-3 是一个平衡点：既能快速响应，又能平滑抖动
            R[elbow_idx, elbow_idx] = 5e-3  # 适度滤波

            # J1-J3 在仿生模式下控制肘部位置，也需要适度滤波
            for i in range(3):  # J1, J2, J3
                R[i, i] = 5e-3  # 适度滤波，比默认的 1e-2 小一半

        # ==========================================
        # 2. 虚拟引导噪声（意图驱动 + 冲突检测 - 论文3.0版本）
        # ==========================================
        # 论文公式：R_virtual(α) = R_min/(α + ε) × I + γ_c × ||Δθ_h - Δθ_v||² × I
        #
        # 物理含义：
        # - 吸附项 R_min/(α + ε)：α → 1 时，方差减小，虚拟引导主导权增加，产生"磁吸"效果
        # - 冲突项 γ_c × ||Δθ_h - Δθ_v||²：当人类指令与虚拟引导冲突时，方差爆炸，允许"挣脱"
        #
        # 优势：反比例函数提供更强的吸附效果，同时保持数值稳定性

        R_min_virtual = self.config.vist_virtual_min_variance if hasattr(self.config, 'vist_virtual_min_variance') else 1e-3
        epsilon = 1e-6  # 避免除零

        # 吸附项：反比例函数
        virtual_variance = R_min_virtual / (self.alpha_smoothed + epsilon)

        # 【核心创新】冲突项：当人类指令与虚拟引导冲突时，增大虚拟引导的噪声
        if human_delta_theta is not None and virtual_delta_theta is not None:
            # 计算冲突强度：||Δθ_human - Δθ_virtual||²
            conflict = np.linalg.norm(human_delta_theta - virtual_delta_theta)**2

            # 冲突增益 γ_c：控制冲突项的影响强度
            conflict_gain = getattr(self.config, 'vist_conflict_gain', 1.0)

            # 添加冲突项到虚拟引导噪声
            # 当冲突大时，R_virtual 增大，降低虚拟引导的权重
            virtual_variance += conflict_gain * conflict

        # 限制最大方差，避免数值问题
        virtual_variance = min(virtual_variance, 1e3)

        R[self.n_joints:, self.n_joints:] = virtual_variance * np.eye(self.n_joints)

        # 【修复】当禁用微分IK时，使用合理的大方差值而不是极端值
        # 避免数值不稳定，同时保持意图驱动的协方差调度机制
        disable_diff_ik = getattr(self.config, 'vist_geometric_solver_disable_differential_ik', False)
        if disable_diff_ik:
            # 使用较大但数值安全的方差，降低虚拟引导权重
            R[self.n_joints:, self.n_joints:] = 1e3 * np.eye(self.n_joints)

        # ==========================================
        # 3. 几何求解器特殊处理
        # ==========================================
        # 【修复】移除几何求解器的硬编码R值调整
        # 应该让意图驱动的协方差调度机制自然发挥作用
        # 几何求解器的高质量输出会通过α因子自动获得更高权重
        # if self.geometric_solver is not None:
        #     # 这部分逻辑已移除，避免与意图驱动机制冲突

        # ==========================================
        # 4. 流形约束（移除R矩阵实现，统一使用Q矩阵的零空间投影）
        # ==========================================
        # 【修复】移除通过R矩阵实现流形约束的逻辑
        # 论文中明确指出流形约束应该通过过程噪声的零空间投影实现（Q矩阵）
        # 在R矩阵中再次实现会导致两种物理机制冲突
        #
        # 原有的R矩阵调整逻辑已移除，流形约束完全由Q矩阵的雅可比投影处理
        # 这确保了单一、清晰的物理机制

        return R

    def detect_intent(self, target_pos, current_pos, velocity, target_quat=None, current_quat=None):
        """
        检测操作意图（完全按照论文公式实现）

        论文公式（Eq. 2-5）：
        - α_geo = exp(-1/2 ξ_err^T W_task ξ_err)  [几何势能]
        - α_vel = 1/(1 + β||ξ_vel||²)             [运动能量]
        - α_dir = 1/2(1 + cos(θ))                 [方向对齐]
        - α_k = σ(w_g·α_geo + w_v·α_vel) · (α_dir)^η  [意图因子]

        意图因子 α ∈ [0, 1]:
        - α → 0: 自由移动模式（远离流形，高速运动，或背离目标）
        - α → 1: 精密操作模式（接近流形，低速运动，且正对目标）

        Args:
            target_pos: 目标位置 (3D)
            current_pos: 当前位置 (3D)
            velocity: 当前速度 (标量或3D向量)
            target_quat: 目标姿态 (可选，用于完整SE(3)误差计算)
            current_quat: 当前姿态 (可选，用于完整SE(3)误差计算)

        Returns:
            alpha: 意图因子
        """
        # ==========================================
        # 0. 检查固定α模式（消融实验）
        # ==========================================
        if hasattr(self.config, 'intent_factor_mode') and self.config.intent_factor_mode == 'fixed':
            # 使用固定α值
            fixed_alpha = self.config.fixed_alpha_value
            self.alpha = fixed_alpha
            # 跳过EMA平滑，直接使用固定值
            self.alpha_smoothed = fixed_alpha
            if self.iteration_count % 100 == 0:  # 每100帧打印一次
                print(f"   🔒 [固定α模式] α = {fixed_alpha:.2f}")
            return self.alpha_smoothed

        # ==========================================
        # 0.1 检查参数覆盖模式（仿真专用）
        # ==========================================
        if hasattr(self.config, 'vist_simulation_use_parameter_override') and \
           self.config.vist_simulation_use_parameter_override:
            # 使用参数覆盖管理器中的α值
            override = self.override_manager.get_override()
            if override.alpha_override is not None:
                self.alpha = override.alpha_override
                # 【修复】即使在参数覆盖模式下，也应该通过EMA平滑过渡
                # 保持C^1连续性，避免控制突变
                smoothing = self.config.vist_intent_smoothing
                self.alpha_smoothed = smoothing * self.alpha_smoothed + (1.0 - smoothing) * self.alpha
                print(f"   🎛️ [参数覆盖] α = {self.alpha:.2f}, α_smoothed = {self.alpha_smoothed:.2f}")
                return self.alpha_smoothed
        # ==========================================
        # 1. 几何势能 α_geo (Eq. 2)
        # ==========================================
        # α_geo = exp(-1/2 ξ_err^T W_task ξ_err)
        #
        # 如果提供了姿态信息，使用完整的6D任务空间误差
        # 否则退化为3D位置误差

        if target_quat is not None and current_quat is not None:
            # 完整SE(3)误差计算
            # 构造SE(3)位姿
            import pinocchio as pin
            target_pose = pin.SE3(pin.Quaternion(target_quat).matrix(), target_pos)
            current_pose = pin.SE3(pin.Quaternion(current_quat).matrix(), current_pos)

            # 计算6D任务空间误差 [δp, δθ]
            xi_err = self._compute_task_space_error_with_lie_algebra(current_pose, target_pose)
        else:
            # 退化为3D位置误差
            xi_err = target_pos - current_pos

        # 从配置读取任务流形度量张量 W_task
        # W_task 是对角矩阵，对不同维度赋予不同权重
        if hasattr(self.config, 'vist_w_task'):
            w_task_config = self.config.vist_w_task
            # 确保维度匹配：如果xi_err是3维，只使用前3个权重
            if len(xi_err) == 3 and len(w_task_config) == 6:
                W_task = np.diag(w_task_config[:3])  # 只使用位置权重
            elif len(xi_err) == 6 and len(w_task_config) == 6:
                W_task = np.diag(w_task_config)  # 使用完整权重
            elif len(xi_err) == len(w_task_config):
                W_task = np.diag(w_task_config)  # 维度匹配
            else:
                # 维度不匹配，使用默认值
                if len(xi_err) == 6:
                    W_task = np.diag([10.0, 10.0, 10.0, 1.0, 1.0, 1.0])
                else:
                    W_task = np.diag([10.0, 10.0, 10.0])
        else:
            # 默认：位置权重高，姿态权重低（因为我们主要关注位置精度）
            if len(xi_err) == 6:
                W_task = np.diag([10.0, 10.0, 10.0, 1.0, 1.0, 1.0])  # [x,y,z,rx,ry,rz]
            else:
                W_task = np.diag([10.0, 10.0, 10.0])  # [x,y,z]

        # 计算马氏距离的平方：ξ_err^T W_task ξ_err
        mahalanobis_sq = xi_err.T @ W_task @ xi_err

        # 几何势能（高斯形式）
        alpha_geo = np.exp(-0.5 * mahalanobis_sq)

        # ==========================================
        # 2. 运动能量 α_vel (Eq. 3)
        # ==========================================
        # α_vel = 1/(1 + β||ξ_vel||²)

        # 计算速度向量和速度大小
        if np.isscalar(velocity):
            speed_sq = velocity**2
            velocity_vec = np.zeros(3)
        else:
            speed_sq = np.linalg.norm(velocity)**2
            velocity_vec = velocity

        # 从配置读取β参数
        beta = self.config.vist_alpha_beta if hasattr(self.config, 'vist_alpha_beta') else 1.0

        # 运动能量（反比例形式）
        alpha_vel = 1.0 / (1.0 + beta * speed_sq)

        # ==========================================
        # 3. 方向对齐 α_dir (Eq. 4)
        # ==========================================
        # α_dir = 1/2(1 + ξ_vel^T ξ_err / (||ξ_vel|| ||ξ_err||))
        #       = 1/2(1 + cos(θ))

        xi_err_norm = np.linalg.norm(xi_err[:3])  # 只使用位置分量计算方向
        velocity_norm = np.linalg.norm(velocity_vec)

        if xi_err_norm > 1e-6 and velocity_norm > 1e-6:
            # 计算余弦相似度
            cos_theta = np.dot(velocity_vec, xi_err[:3]) / (velocity_norm * xi_err_norm)
            cos_theta = np.clip(cos_theta, -1.0, 1.0)

            # 方向对齐因子
            alpha_dir = 0.5 * (1.0 + cos_theta)
        else:
            # 速度太小或误差太小，默认为对齐
            alpha_dir = 1.0

        # ==========================================
        # 4. 意图因子融合 α_k (Eq. 5)
        # ==========================================
        # α_k = σ(w_g·α_geo + w_v·α_vel) · (α_dir)^η

        # 从配置读取权重
        w_g = self.config.vist_w_geo if hasattr(self.config, 'vist_w_geo') else 0.5
        w_v = self.config.vist_w_vel if hasattr(self.config, 'vist_w_vel') else 0.5
        eta = self.config.vist_alpha_alignment_power if hasattr(self.config, 'vist_alpha_alignment_power') else 2.0

        # 状态先验：几何势能和运动能量的加权和
        state_prior = w_g * alpha_geo + w_v * alpha_vel

        # Sigmoid归一化
        state_prior_normalized = 1.0 / (1.0 + np.exp(-5.0 * (state_prior - 0.5)))

        # 主动门控：方向对齐的幂次
        active_gating = alpha_dir ** eta

        # 非线性融合
        self.alpha = state_prior_normalized * active_gating

        # ==========================================
        # 5. EMA 平滑
        # ==========================================
        smoothing = self.config.vist_intent_smoothing
        self.alpha_smoothed = smoothing * self.alpha_smoothed + (1.0 - smoothing) * self.alpha

        return self.alpha_smoothed

    def _compute_task_space_error_with_lie_algebra(self, current_pose, target_pose):
        """
        计算任务空间误差（使用李代数处理姿态）

        这是混合方案的核心：
        - 状态空间：关节空间 x = [q, q̇]
        - 观测空间：任务空间 SE(3)
        - 姿态误差：使用李代数 δθ = log_SO3(R_current^T R_target)

        Args:
            current_pose: 当前末端位姿 (pin.SE3)
            target_pose: 目标位姿 (pin.SE3)

        Returns:
            δx: [δp, δθ] ∈ ℝ^6，其中 δθ ∈ so(3)
        """
        # 1. 位置误差（欧氏空间）
        δp = target_pose.translation - current_pose.translation

        # 2. 姿态误差（李代数）
        # 计算相对旋转：R_rel = R_current^T @ R_target
        R_current = current_pose.rotation
        R_target = target_pose.rotation
        R_rel = R_current.T @ R_target

        # 使用 Pinocchio 的 log3 函数将 SO(3) 映射到 so(3)
        # δθ = log_SO3(R_rel) ∈ ℝ^3 (轴角表示)
        δθ = pin.log3(R_rel)

        # 3. 组合为 6D 任务空间误差
        δx = np.concatenate([δp, δθ])

        return δx

    def compute_differential_ik(self, target_pos, target_quat=None):
        """
        计算微分 IK 观测：Δθ = J†·Δx

        这是 VIST 的核心创新：不计算绝对关节角，而是计算增量
        - 避免全局 IK 的多解问题
        - 天然保证连续性
        - 雅可比伪逆自动寻找最小动能路径

        Args:
            target_pos: 目标位置 (3D)
            target_quat: 目标四元数 (可选，4D)

        Returns:
            delta_theta: 关节角度增量 (n_joints,)
        """
        try:
            # 获取当前关节角度（受控关节）
            q_controlled = self.state[:self.n_joints]

            # 扩展到完整模型
            q_full = self._get_full_q_from_controlled(q_controlled)

            # 确保 q_full 是有效的配置
            if not np.all(np.isfinite(q_full)):
                print(f"⚠️ [VIST] compute_differential_ik: q_full 包含无效值")
                return np.zeros(self.n_joints)

            # 正运动学：计算当前末端位置
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

            ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
            current_pos = ee_placement.translation

            # 计算位置误差
            delta_x = target_pos - current_pos

            # 计算雅可比矩阵
            J_full = pin.computeFrameJacobian(
                self.ik_solver.model,
                self.ik_solver.data,
                q_full,
                self.ik_solver.ee_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )

            # 只使用位置部分（前3行）和受控关节
            J = J_full[:3, self.ik_solver.controlled_indices]

            # 阻尼伪逆：J† = J^T @ (J @ J^T + λ^2 * I)^(-1)
            damping = self.config.vist_differential_ik_damping
            JJT = J @ J.T
            damping_matrix = damping**2 * np.eye(3)
            J_pinv = J.T @ inv(JJT + damping_matrix)

            # 微分观测：Δθ = J†·Δx
            delta_theta = J_pinv @ delta_x

            # 返回目标关节角度（绝对值）
            q_target = q_controlled + delta_theta

            return q_target

        except Exception as e:
            print(f"⚠️ [VIST] compute_differential_ik 错误: {e}")
            import traceback
            traceback.print_exc()
            return np.zeros(self.n_joints)

    def compute_differential_ik_with_orientation(self, target_pos, target_quat):
        """
        计算带姿态的微分 IK 观测：Δθ = J†·δx

        这是混合方案的实现：
        - 使用李代数计算任务空间姿态误差
        - 通过完整的 6D 雅可比矩阵转换到关节空间
        - 保持关节空间 Kalman 滤波的优势

        Args:
            target_pos: 目标位置 (3D)
            target_quat: 目标四元数 [x, y, z, w]

        Returns:
            delta_theta: 关节角度增量 (n_joints,)
        """
        try:
            # 1. 获取当前关节角度
            q_controlled = self.state[:self.n_joints]
            q_full = self._get_full_q_from_controlled(q_controlled)

            # 2. 正运动学：计算当前末端位姿
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

            current_pose = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]

            # 3. 构建目标位姿 (SE3)
            target_rot = pin.Quaternion(target_quat[3], target_quat[0], target_quat[1], target_quat[2]).toRotationMatrix()
            target_pose = pin.SE3(target_rot, target_pos)

            # 4. 使用李代数计算任务空间误差
            δx = self._compute_task_space_error_with_lie_algebra(current_pose, target_pose)

            # 5. 计算完整的 6D 雅可比矩阵
            J_full = pin.computeFrameJacobian(
                self.ik_solver.model,
                self.ik_solver.data,
                q_full,
                self.ik_solver.ee_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )

            # 6. 提取受控关节的雅可比（6行 × n_joints列）
            J = J_full[:, self.ik_solver.controlled_indices]

            # 7. 阻尼伪逆：J† = J^T @ (J @ J^T + λ^2 * I)^(-1)
            damping = self.config.vist_differential_ik_damping
            JJT = J @ J.T
            damping_matrix = damping**2 * np.eye(6)  # 6D 阻尼矩阵
            J_pinv = J.T @ inv(JJT + damping_matrix)

            # 8. 微分观测：Δθ = J†·δx
            delta_theta = J_pinv @ δx

            # 返回目标关节角度（绝对值）
            q_target = q_controlled + delta_theta

            return q_target

        except Exception as e:
            print(f"⚠️ [VIST] compute_differential_ik_with_orientation 错误: {e}")
            import traceback
            traceback.print_exc()
            return np.zeros(self.n_joints)

    def predict(self):
        """
        卡尔曼滤波预测步骤

        利用恒速模型进行前瞻预测，补偿传输滞后：
        - x_pred = F @ x
        - P_pred = F @ P @ F^T + Q
        """
        # 状态预测
        self.state = self.F @ self.state

        # 协方差预测
        self.P = self.F @ self.P @ self.F.T + self.Q

    def compute_human_delta_theta(self, target_pos, previous_target_pos):
        """
        从人手位置变化计算目标关节角度

        这是 VIST 的关键创新：将人手运动直接转换为关节角度
        - 使用微分 IK 将笛卡尔空间的位置变化转换为关节空间
        - 与虚拟引导观测独立，提供人类意图的直接表达

        Args:
            target_pos: 当前人手目标位置 (3D)
            previous_target_pos: 上一帧人手目标位置 (3D)

        Returns:
            q_target: 目标关节角度（绝对值，不是增量）
        """
        # 计算人手位置变化
        delta_x_human = target_pos - previous_target_pos

        # 获取当前关节角度
        q_controlled = self.state[:self.n_joints]
        q_full = self._get_full_q_from_controlled(q_controlled)

        # 计算雅可比矩阵
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        J_full = pin.computeFrameJacobian(
            self.ik_solver.model,
            self.ik_solver.data,
            q_full,
            self.ik_solver.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        # 只使用位置部分和受控关节
        J = J_full[:3, self.ik_solver.controlled_indices]

        # 阻尼伪逆
        damping = self.config.vist_differential_ik_damping
        JJT = J @ J.T
        damping_matrix = damping**2 * np.eye(3)
        J_pinv = J.T @ inv(JJT + damping_matrix)

        # 人类指令增量：Δθ_human = J† @ Δx_human
        delta_theta = J_pinv @ delta_x_human

        # 返回目标关节角度（绝对值），而不是增量
        # 这样卡尔曼滤波器可以通过 innovation = z - H @ state 正确计算
        q_target = self.state[:self.n_joints] + delta_theta

        return q_target

    def compute_human_delta_theta_from_elbow(self, shoulder_pos, elbow_pos, wrist_pos, target_orientation=None):
        """
        从肘部位置计算目标关节角度（使用几何解析解）

        这是 VIST 的肘部约束集成：
        - 使用几何解析解计算臂部配置（q1-q4）
        - 使用欧拉角分解计算腕部姿态（q5-q7）
        - 返回目标关节角度（绝对值）

        Args:
            shoulder_pos: 肩部位置 [x, y, z] (numpy array)
            elbow_pos: 肘部位置 [x, y, z] (numpy array)
            wrist_pos: 腕部位置 [x, y, z] (numpy array)
            target_orientation: 目标末端姿态（可选，四元数或旋转矩阵）

        Returns:
            q_target: 目标关节角度（绝对值，不是增量）
        """
        if self.geometric_solver is None:
            raise ValueError("几何求解器未初始化，无法使用肘部约束")

        # 1. 使用几何解析解计算目标关节角度
        # 传递alpha参数以支持动态腕部解锁
        # ✅ 传递当前关节角度，用于wrist_locked模式
        q_current = self.state[:self.n_joints]  # 从状态向量提取当前关节角度
        q_decoupled = self.geometric_solver.solve(
            shoulder_pos, elbow_pos, wrist_pos, target_orientation,
            alpha=self.alpha_smoothed, q_current=q_current
        )

        # 2. 直接返回目标关节角度（绝对值，不是增量）
        # 注意：这里返回的是绝对角度，卡尔曼滤波器会通过 H 矩阵处理
        # innovation = z - H @ state = q_decoupled - state
        return q_decoupled

    def compute_biomimetic_observation(self, shoulder_pos, elbow_pos, wrist_pos, target_pos):
        """
        仿生多任务观测模型（3+4解耦 - 分层控制版本）

        核心思想：满足构型就能满足位置（因为有长度归一化）

        运动学链条（分层控制）：
        1. J1-J3（肩部）→ 控制肘部位置到达目标肘部位置
        2. J4（肘部）   → 控制肘部角度匹配人体肘部角度
        3. J5-J7（腕部）→ 控制末端位置到达目标末端位置

        这样可以避免关节冲突，肘部不会被"粘住"。

        Args:
            shoulder_pos: 人体肩部位置 [x, y, z]
            elbow_pos: 人体肘部位置 [x, y, z]
            wrist_pos: 人体腕部位置 [x, y, z]
            target_pos: 目标末端位置 [x, y, z]

        Returns:
            z_observation: 完整的观测增量 (n_joints,)
        """
        try:
            # 初始化观测向量
            z_observation = np.zeros(self.n_joints)

            # ==========================================
            # 层级 1: 肩部关节（J1-J3）- 控制肘部位置
            # ==========================================
            # 计算肘部位置误差
            current_elbow_pos = self._estimate_current_elbow_position()
            delta_elbow_pos = elbow_pos - current_elbow_pos

            # 【修复】移除预滤波器，让卡尔曼滤波器完成所有滤波工作
            # 论文强调VIST是"物理层面的数据正则化器"，应该通过
            # 自适应卡尔曼滤波的协方差调度来实现滤波，而不是前端EMA
            # 预滤波会引入相位滞后，违背论文批判的"纯时域滤波的局限"

            # 使用微分IK计算肩部关节增量（只用前3个关节）
            z_shoulder = self._compute_shoulder_joints_for_elbow(delta_elbow_pos)
            z_observation[:3] = z_shoulder

            # ==========================================
            # 层级 2: 肘部关节（J4）- 控制肘部角度
            # ==========================================
            # 计算人体肘部角度（余弦定理）
            vec_upper = elbow_pos - shoulder_pos
            vec_lower = wrist_pos - elbow_pos
            cos_angle = np.dot(vec_upper, vec_lower) / (
                np.linalg.norm(vec_upper) * np.linalg.norm(vec_lower) + 1e-6
            )
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            human_elbow_angle = np.arccos(cos_angle)

            # 【修复】移除肘部角度的预滤波器
            # 让卡尔曼滤波器通过意图驱动的协方差调度来处理抖动

            # 机器人当前肘部角度
            robot_elbow_angle = self.state[3]  # J4 = 索引3 (Right_Elbow_Pitch_Joint)

            # 肘部角度增量（不再增强，避免压制肩部运动）
            elbow_delta = human_elbow_angle - robot_elbow_angle
            z_observation[3] = elbow_delta  # 1.0x，与其他关节平衡

            # ==========================================
            # 层级 3: 腕部关节（J5-J7）- 控制末端位置
            # ==========================================
            # 计算末端位置误差
            current_wrist_pos = self._get_current_end_effector_position()
            delta_wrist_pos = target_pos - current_wrist_pos

            # 使用微分IK计算腕部关节增量（只用后3个关节）
            z_wrist = self._compute_wrist_joints_for_endeffector(delta_wrist_pos)
            z_observation[4:7] = z_wrist

            return z_observation

        except Exception as e:
            print(f"⚠️ [VIST] compute_biomimetic_observation 错误: {e}")
            import traceback
            traceback.print_exc()
            # 返回零向量作为安全回退
            return np.zeros(self.n_joints)

    def _estimate_current_elbow_position(self):
        """估算当前机器人肘部位置"""
        q_controlled = self.state[:self.n_joints]
        q_full = self._get_full_q_from_controlled(q_controlled)

        # 正运动学
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        # 尝试获取肘部frame
        try:
            # 检查 frame 是否存在
            if self.ik_solver.model.existFrame("Right_Elbow_Pitch_Link"):
                elbow_frame_id = self.ik_solver.model.getFrameId("Right_Elbow_Pitch_Link")
                elbow_pos = self.ik_solver.data.oMf[elbow_frame_id].translation
            else:
                # Frame 不存在，使用配置参数估算
                raise ValueError("Right_Elbow_Pitch_Link frame not found")
        except Exception as e:
            # 回退：使用配置参数估算
            print(f"⚠️ [VIST] 肘部 frame 不存在，使用几何估算: {e}")
            shoulder_pos = np.array(self.config.robot_shoulder_position)
            upper_arm_length = self.config.robot_arm_lengths['upper']
            q1, q2 = q_controlled[:2]
            elbow_pos = shoulder_pos + upper_arm_length * np.array([
                np.cos(q1) * np.cos(q2),
                np.sin(q2),
                np.sin(q1) * np.cos(q2)
            ])

        return elbow_pos

    def _compute_shoulder_joints_for_elbow(self, delta_elbow_pos):
        """
        计算肩部关节增量以控制肘部位置

        使用肩部关节（J1-J3）的雅可比矩阵
        """
        try:
            q_controlled = self.state[:self.n_joints]
            q_full = self._get_full_q_from_controlled(q_controlled)

            # 计算肘部frame的雅可比矩阵
            try:
                # 检查 frame 是否存在
                if not self.ik_solver.model.existFrame("Right_Elbow_Pitch_Link"):
                    raise ValueError("Right_Elbow_Pitch_Link frame not found in URDF")

                elbow_frame_id = self.ik_solver.model.getFrameId("Right_Elbow_Pitch_Link")
                pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
                pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

                J_full = pin.computeFrameJacobian(
                    self.ik_solver.model,
                    self.ik_solver.data,
                    q_full,
                    elbow_frame_id,
                    pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
                )

                # 只使用位置部分（前3行）和肩部关节的列
                # controlled_indices = [7, 8, 9, 10, 11, 12, 13]
                # 肩部关节索引：[7, 8, 9]
                shoulder_indices = self.ik_solver.controlled_indices[:3]
                J_shoulder = J_full[:3, shoulder_indices]

                # 阻尼伪逆
                damping = self.config.vist_differential_ik_damping
                JJT = J_shoulder @ J_shoulder.T
                damping_matrix = damping**2 * np.eye(3)
                J_pinv = J_shoulder.T @ inv(JJT + damping_matrix)

                # 计算肩部关节增量
                z_shoulder = J_pinv @ delta_elbow_pos

            except Exception as e:
                # 回退：简化的几何估算
                print(f"⚠️ 肩部雅可比计算失败: {e}，使用简化估算")
                z_shoulder = np.zeros(3)
                # 简化：假设主要由J1和J2控制
                z_shoulder[0] = delta_elbow_pos[0] * 0.5  # Pitch
                z_shoulder[1] = delta_elbow_pos[1] * 0.5  # Roll

            return z_shoulder

        except Exception as e:
            print(f"⚠️ [VIST] _compute_shoulder_joints_for_elbow 严重错误: {e}")
            import traceback
            traceback.print_exc()
            return np.zeros(3)

    def _compute_wrist_joints_for_endeffector(self, delta_wrist_pos):
        """
        计算腕部关节增量以控制末端位置

        使用腕部关节（J5-J7）的雅可比矩阵
        """
        try:
            q_controlled = self.state[:self.n_joints]
            q_full = self._get_full_q_from_controlled(q_controlled)

            # 计算末端执行器的雅可比矩阵
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

            J_full = pin.computeFrameJacobian(
                self.ik_solver.model,
                self.ik_solver.data,
                q_full,
                self.ik_solver.ee_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )

            # 只使用位置部分（前3行）和腕部关节（后3列）
            wrist_indices = self.ik_solver.controlled_indices[4:7]

            # 调试：检查维度
            if J_full.shape[1] <= max(wrist_indices):
                print(f"⚠️ [VIST] Jacobian 维度不匹配!")
                print(f"   J_full.shape: {J_full.shape}")
                print(f"   wrist_indices: {wrist_indices}")
                print(f"   controlled_indices: {self.ik_solver.controlled_indices}")
                # 使用安全的索引
                wrist_indices = list(range(4, min(7, J_full.shape[1])))

            J_wrist = J_full[:3, wrist_indices]

            # 阻尼伪逆
            damping = self.config.vist_differential_ik_damping
            JJT = J_wrist @ J_wrist.T
            damping_matrix = damping**2 * np.eye(3)
            J_pinv = J_wrist.T @ inv(JJT + damping_matrix)

            # 计算腕部关节增量
            z_wrist = J_pinv @ delta_wrist_pos

            return z_wrist

        except Exception as e:
            print(f"⚠️ [VIST] _compute_wrist_joints_for_endeffector 错误: {e}")
            import traceback
            traceback.print_exc()
            return np.zeros(3)

    def _get_robot_arm_plane_normal(self):
        """
        计算机器人当前臂平面的法向量

        通过正运动学获取肩、肘、腕三点位置，计算平面法向量

        Returns:
            n_robot: 机器人臂平面法向量 (3,)
        """
        # 获取当前关节角度
        q_controlled = self.state[:self.n_joints]
        q_full = self._get_full_q_from_controlled(q_controlled)

        # 正运动学
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        # 方法1：尝试使用URDF中定义的frame（如果存在）
        try:
            shoulder_frame_id = self.ik_solver.model.getFrameId("Right_Shoulder_Pitch_Link")
            elbow_frame_id = self.ik_solver.model.getFrameId("Right_Elbow_Pitch_Link")
            wrist_frame_id = self.ik_solver.ee_frame_id

            shoulder_pos = self.ik_solver.data.oMf[shoulder_frame_id].translation
            elbow_pos = self.ik_solver.data.oMf[elbow_frame_id].translation
            wrist_pos = self.ik_solver.data.oMf[wrist_frame_id].translation

        except Exception:
            # 方法2：使用配置文件中的臂长参数和关节角度估算
            # 这是回退方案，当URDF中没有定义相应frame时使用
            shoulder_pos = np.array(self.config.robot_shoulder_position)

            # 从配置文件读取臂长参数
            upper_arm_length = self.config.robot_arm_lengths['upper']
            forearm_length = self.config.robot_arm_lengths['forearm']

            # 使用关节角度估算（简化的几何模型）
            q1, q2, q3, q4 = q_controlled[:4]

            # 肘部位置估算（基于球坐标系）
            elbow_pos = shoulder_pos + upper_arm_length * np.array([
                np.cos(q1) * np.cos(q2),
                np.sin(q2),
                np.sin(q1) * np.cos(q2)
            ])

            # 腕部位置估算
            wrist_pos = elbow_pos + forearm_length * np.array([
                np.cos(q1 + q4) * np.cos(q2),
                np.sin(q2),
                np.sin(q1 + q4) * np.cos(q2)
            ])

        # 计算臂平面法向量
        vec_upper = elbow_pos - shoulder_pos
        vec_lower = wrist_pos - elbow_pos
        n_robot = np.cross(vec_upper, vec_lower)
        n_robot_norm = np.linalg.norm(n_robot)

        if n_robot_norm > 1e-6:
            n_robot = n_robot / n_robot_norm
        else:
            n_robot = np.array([0, 0, 1])

        return n_robot

    def update(self, target_pos, target_quat=None, human_delta_theta=None, previous_target_pos=None,
               elbow_pos=None, shoulder_pos=None, use_biomimetic=False):
        """
        卡尔曼滤波更新步骤

        融合人类指令和虚拟引导：
        - 计算卡尔曼增益 K
        - 更新状态估计 x = x + K @ (z - H @ x)
        - 更新协方差 P = (I - K @ H) @ P

        Args:
            target_pos: 目标位置 (3D) - 腕部/手部位置
            target_quat: 目标四元数 (可选)
            human_delta_theta: 人类指令增量 (可选，如果为 None 则自动计算)
            previous_target_pos: 上一帧目标位置 (可选，用于计算人类指令)
            elbow_pos: 肘部位置 (可选，用于几何解析解)
            shoulder_pos: 肩部位置 (可选，用于几何解析解)
            use_biomimetic: 是否使用仿生多任务观测模型（默认False）

        Returns:
            q_solution: 估计的关节角度
            success: 是否成功
        """
        # 1. 计算微分 IK 观测（虚拟引导）
        # 检查是否禁用微分IK
        disable_diff_ik = getattr(self.config, 'vist_geometric_solver_disable_differential_ik', False)

        if self.iteration_count % 50 == 0:  # 每50次迭代打印一次
            print(f"🔧 [VIST] 微分IK状态: {'已禁用' if disable_diff_ik else '已启用'}", flush=True)

        if disable_diff_ik:
            # 禁用微分IK：使用零向量
            delta_theta_virtual = np.zeros(self.n_joints)
        else:
            # 检查是否启用姿态控制
            use_orientation = getattr(self.config, 'vist_use_orientation_control', False)

            if use_orientation and target_quat is not None:
                # 使用带姿态的微分 IK（6D雅可比 + 李代数）
                delta_theta_virtual = self.compute_differential_ik_with_orientation(target_pos, target_quat)
            else:
                # 使用标准微分 IK（只控制位置，3D雅可比）
                delta_theta_virtual = self.compute_differential_ik(target_pos, target_quat)

        # 2. 计算人类指令观测
        if human_delta_theta is None:
            # ==========================================
            # 模式选择：仿生多任务 vs 几何解析 vs 标准微分IK
            # ==========================================
            if use_biomimetic and elbow_pos is not None and shoulder_pos is not None:
                # 【仿生模式】：使用3+4解耦的分层控制观测
                wrist_pos = target_pos  # 腕部位置就是目标位置
                human_delta_theta = self.compute_biomimetic_observation(
                    shoulder_pos, elbow_pos, wrist_pos, target_pos
                )
                # 注意：新版本直接返回完整的观测向量，不需要额外融合

            elif self.geometric_solver is not None and elbow_pos is not None and shoulder_pos is not None:
                # 【几何解析模式】：使用完整的几何解耦（需要几何求解器）
                human_delta_theta = self.compute_human_delta_theta_from_elbow(
                    shoulder_pos, elbow_pos, target_pos, target_quat
                )
            elif previous_target_pos is not None:
                # 【标准微分IK模式】：从人手位置变化计算人类指令
                human_delta_theta = self.compute_human_delta_theta(target_pos, previous_target_pos)
            else:
                # 如果没有历史数据，使用零向量
                human_delta_theta = np.zeros(self.n_joints)

        # 3. 构建观测向量
        z = np.concatenate([human_delta_theta, delta_theta_virtual])

        # 4. 构建观测噪声协方差（意图驱动 + 冲突检测）
        R = self._build_observation_noise_covariance(
            use_biomimetic=use_biomimetic,
            human_delta_theta=human_delta_theta,
            virtual_delta_theta=delta_theta_virtual
        )

        # 5. 计算卡尔曼增益
        # K = P @ H^T @ (H @ P @ H^T + R)^(-1)
        S = self.H @ self.P @ self.H.T + R  # 创新协方差
        K = self.P @ self.H.T @ inv(S)  # 卡尔曼增益

        # 5. 更新状态
        innovation = z - self.H @ self.state
        self.state = self.state + K @ innovation

        # 6. 更新协方差
        I = np.eye(self.state_dim)
        self.P = (I - K @ self.H) @ self.P

        # 注意：流形约束通过R矩阵在观测层面实现，不需要后处理投影

        # 7. 关节限位（只对受控关节）
        q_solution = self.state[:self.n_joints]

        # 提取受控关节的限位
        q_min_controlled = np.array([self.ik_solver.q_min[idx] for idx in self.ik_solver.controlled_indices])
        q_max_controlled = np.array([self.ik_solver.q_max[idx] for idx in self.ik_solver.controlled_indices])

        q_solution = np.clip(q_solution, q_min_controlled, q_max_controlled)
        self.state[:self.n_joints] = q_solution

        # 8. 更新迭代计数
        self.iteration_count += 1

        return q_solution, True

    def solve(self, target_pos, target_quat=None, q_init=None, elbow_pos=None, shoulder_pos=None):
        """
        VIST 求解主接口（兼容 IK 求解器接口）

        Args:
            target_pos: 目标位置 (3D) - 腕部/手部位置
            target_quat: 目标四元数 (可选)
            q_init: 初始关节角度 (可选，用于初始化状态)
                   可以是完整模型维度或受控关节维度
            elbow_pos: 肘部位置 (可选，用于几何解析解)
            shoulder_pos: 肩部位置 (可选，用于几何解析解)

        Returns:
            q_solution: 关节角度解
            success: 是否成功
            error: 位置误差（用于兼容性）
        """
        try:
            print(f"🔍 [VIST] solve() 开始 (iteration={self.iteration_count})")

            # 如果提供了初始猜测，初始化状态
            if q_init is not None and self.iteration_count == 0:
                print(f"   初始化状态: q_init shape={np.array(q_init).shape}")
                q_init = np.array(q_init, dtype=np.float64)

                # 检查维度并提取受控关节
                if len(q_init) == self.ik_solver.model.nq:
                    # 完整模型维度，提取受控关节
                    q_controlled = np.zeros(self.n_joints)
                    for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                        if ctrl_idx < len(q_init):
                            q_controlled[i] = q_init[ctrl_idx]
                    self.state[:self.n_joints] = q_controlled
                elif len(q_init) == self.n_joints:
                    # 已经是受控关节维度
                    self.state[:self.n_joints] = q_init
                else:
                    # 维度不匹配，使用零初始化
                    self.state[:self.n_joints] = np.zeros(self.n_joints)

                self.state[self.n_joints:] = 0.0  # 初始速度为零
                print(f"   状态初始化完成: state[:7]={self.state[:7]}")

            # 1. 预测步骤
            print(f"   步骤 1: 预测")
            self.predict()

            # 2. 意图检测
            print(f"   步骤 2: 意图检测")
            current_pos = self._get_current_end_effector_position()
            print(f"   当前末端位置: {current_pos}")
            velocity = self.state[self.n_joints:self.n_joints+3]  # 前3个速度分量
            self.detect_intent(target_pos, current_pos, velocity)

            # 3. 从配置读取几何求解器和仿生观测的启用状态
            use_geometric_solver = self.config.vist_geometric_solver_enabled
            use_biomimetic = self.config.vist_biomimetic_enabled
            print(f"   几何求解器: {use_geometric_solver}, 仿生观测: {use_biomimetic}")

            # 4. 如果启用几何求解器且提供了肘部和肩部位置，计算人类指令
            human_delta_theta = None
            if use_geometric_solver and self.geometric_solver is not None and \
               elbow_pos is not None and shoulder_pos is not None:
                # 使用几何解析解计算臂部配置
                wrist_pos = target_pos  # 腕部位置就是目标位置
                human_delta_theta = self.compute_human_delta_theta_from_elbow(
                    shoulder_pos, elbow_pos, wrist_pos, target_quat
                )

            # 5. 更新步骤（传递肘部和肩部位置以及配置参数）
            print(f"   步骤 3: 更新")
            q_solution, success = self.update(
                target_pos,
                target_quat,
                human_delta_theta=human_delta_theta,
                previous_target_pos=self.previous_target_pos,
                elbow_pos=elbow_pos,
                shoulder_pos=shoulder_pos,
                use_biomimetic=use_biomimetic
            )

            # 6. 保存当前目标位置作为下一帧的历史
            self.previous_target_pos = target_pos.copy()

            # 7. 计算误差（用于统计）
            print(f"   步骤 4: 计算误差")
            q_full = self._get_full_q_from_controlled(q_solution)
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
            ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
            current_pos = ee_placement.translation
            error = np.linalg.norm(target_pos - current_pos)

            print(f"✅ [VIST] solve() 完成 (error={error:.4f}m)")
            return q_solution, success, error

        except Exception as e:
            print(f"❌ [VIST] solve() 严重错误: {e}")
            import traceback
            traceback.print_exc()
            # 返回当前状态作为安全回退
            return self.state[:self.n_joints].copy(), False, 999.0

    def _get_full_q_from_controlled(self, q_controlled):
        """
        将受控关节角度扩展到完整模型关节角度

        Args:
            q_controlled: 受控关节角度 (n_joints,)

        Returns:
            q_full: 完整模型关节角度 (model.nq,)
        """
        try:
            q_full = pin.neutral(self.ik_solver.model).copy()

            # 确保 q_controlled 是有效的
            if not np.all(np.isfinite(q_controlled)):
                print(f"⚠️ [VIST] q_controlled 包含无效值: {q_controlled}")
                return q_full  # 返回中立配置

            for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                if i < len(q_controlled) and ctrl_idx < len(q_full):
                    q_full[ctrl_idx] = q_controlled[i]

            return q_full
        except Exception as e:
            print(f"⚠️ [VIST] _get_full_q_from_controlled 错误: {e}")
            import traceback
            traceback.print_exc()
            return pin.neutral(self.ik_solver.model)

    def _apply_manifold_projection(self, target_pos, target_quat=None):
        """
        应用流形约束投影：保持X、Y与目标一致，只允许Z方向自由运动

        Args:
            target_pos: 目标位置（用于获取X、Y参考）
            target_quat: 目标姿态（用于姿态约束）
        """
        try:
            # 获取当前关节配置
            q_controlled = self.state[:self.n_joints].copy()
            q_full = self._get_full_q_from_controlled(q_controlled)

            # 计算当前末端位置
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
            ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
            current_pos = ee_placement.translation.copy()
            current_rot = ee_placement.rotation.copy()

            # 构造约束目标：使用目标的X、Y，保持当前的Z
            constrained_pos = target_pos.copy()
            constrained_pos[2] = current_pos[2]  # 保持当前Z坐标

            # 姿态约束：使用目标姿态（如果提供）或保持当前姿态
            if target_quat is not None:
                constrained_quat = target_quat
            else:
                constrained_quat = pin.Quaternion(current_rot).coeffs()

            # 使用IK求解器计算满足约束的关节角度
            q_constrained, success, error = self.ik_solver.solve(
                target_pos=constrained_pos,
                target_quat=constrained_quat,
                q_init=q_full,
                max_iter=10,
                tol=1e-3,
                damping=1e-2
            )

            if success:
                # 提取受控关节
                q_controlled_new = np.zeros(self.n_joints)
                for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                    if ctrl_idx < len(q_constrained):
                        q_controlled_new[i] = q_constrained[ctrl_idx]

                # 更新状态
                self.state[:self.n_joints] = q_controlled_new
                print(f"   ✅ [流形约束] 投影成功 (error={error:.4f}m, target_xy=[{target_pos[0]:.3f}, {target_pos[1]:.3f}], current_z={current_pos[2]:.3f})")
            else:
                print(f"   ⚠️ [流形约束] 投影失败，保持原状态")

        except Exception as e:
            print(f"   ⚠️ [流形约束] 投影错误: {e}")
            import traceback
            traceback.print_exc()

    def _get_current_end_effector_position(self):
        """获取当前末端执行器位置"""
        try:
            q_controlled = self.state[:self.n_joints]
            q_full = self._get_full_q_from_controlled(q_controlled)

            # 确保 q_full 是有效的配置
            if not np.all(np.isfinite(q_full)):
                print(f"⚠️ [VIST] q_full 包含无效值，使用中立配置")
                q_full = pin.neutral(self.ik_solver.model)

            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
            ee_placement = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]
            return ee_placement.translation
        except Exception as e:
            print(f"⚠️ [VIST] _get_current_end_effector_position 错误: {e}")
            import traceback
            traceback.print_exc()
            # 返回肩部位置作为安全回退
            return np.array(self.config.robot_shoulder_position)

    def reset(self):
        """重置滤波器状态"""
        self.state = np.zeros(self.state_dim)
        self.P = np.eye(self.state_dim)
        self.P[:self.n_joints, :self.n_joints] *= self.config.vist_initial_state_variance
        self.P[self.n_joints:, self.n_joints:] *= self.config.vist_initial_velocity_variance
        self.alpha = 0.0
        self.alpha_smoothed = 0.0
        self.previous_target_pos = None  # 重置历史位置
        # 【修复】移除预滤波器变量的重置
        self.iteration_count = 0


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试 VIST Kalman Filter...")
    print("请运行 scripts/simulate_full_flow.py 进行完整测试")
