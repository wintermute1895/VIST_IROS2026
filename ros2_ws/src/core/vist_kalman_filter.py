#!/usr/bin/env python3
"""
VIST Kalman Filter - 基于意图感知的遥操作统一状态估计框架

核心功能（完整重写版本）：
1. 意图检测（圆柱形2D距离门控）
2. 观测噪声整形（动态R矩阵调度）
3. 过程噪声协方差回拉（任务空间流形约束 → 关节空间）
4. 卡尔曼滤波状态估计（关节空间）

四大工程化魔改：
1. 纯前馈正向运动学（使用影子状态，不用真实反馈）
2. 固定阻尼最小二乘法（DLS替代伪逆）
3. 保留粘滞感的子空间方差（Σ_cons不为0）
4. 圆柱形2D距离门控（Z轴高度阈值）

参考：docs/SESSION_HANDOVER_2026-03-02.md (行134-220)
"""

import numpy as np
import pinocchio as pin
from scipy.linalg import inv
import time
import csv
import os
from datetime import datetime


class VISTKalmanFilter:
    """
    VIST 卡尔曼滤波器（完整重写版本）

    状态向量: x = [θ, θ̇]^T  (14维)
    - θ: 7个关节角度
    - θ̇: 7个关节速度

    过程模型: x(k+1) = F·x(k) + w(k)
    - F: 恒速模型状态转移矩阵
    - w: 意图驱动的过程噪声（通过协方差回拉）

    观测模型: z = H·x + v
    - z: 人类指令和虚拟引导的融合观测
    - v: 意图驱动的观测噪声
    """

    def __init__(self, ik_solver, config, geometric_solver=None):
        """
        初始化 VIST 卡尔曼滤波器

        Args:
            ik_solver: IK 求解器实例（用于正向运动学和雅可比计算）
            config: 配置对象（必须包含所有VIST参数）
            geometric_solver: 几何解析求解器（可选）
        """
        self.ik_solver = ik_solver
        self.config = config
        self.geometric_solver = geometric_solver

        # ==========================================
        # 1. 状态空间维度
        # ==========================================
        self.n_joints = config.vist_n_joints
        self.state_dim = config.vist_state_dim  # 2 * n_joints

        # ==========================================
        # 2. 从配置文件读取所有参数
        # ==========================================
        # 2.1 过程模型参数
        self.dt = config.vist_filter_system_dt  # 时间步长

        # 2.2 观测模型参数
        self.use_orientation_control = config.vist_observation_use_orientation_control
        self.fusion_method = config.vist_observation_fusion_method
        self.human_base_variance = config.vist_observation_human_base_variance
        self.human_lambda = config.vist_observation_human_lambda
        self.virtual_min_variance = config.vist_observation_virtual_min_variance
        self.conflict_gain = config.vist_observation_conflict_gain
        self.differential_ik_damping = config.vist_observation_differential_ik_damping

        # 2.3 意图检测参数
        self.w_task = np.array(config.vist_intent_w_task)  # 任务流形度量张量
        self.alpha_beta = config.vist_intent_alpha_beta  # 运动能量参数
        self.w_geo = config.vist_intent_w_geo  # 几何势能权重
        self.w_vel = config.vist_intent_w_vel  # 速度权重
        self.alpha_alignment_power = config.vist_intent_alpha_alignment_power  # 方向对齐指数
        self.intent_smoothing = config.vist_intent_intent_smoothing  # 意图平滑系数

        # 2.4 任务空间方差参数（粘滞感）
        self.free_variance_xyz = np.array(config.vist_task_covariance_free_variance_xyz)
        self.free_variance_rpy = np.array(config.vist_task_covariance_free_variance_rpy)
        self.cons_variance_xyz = np.array(config.vist_task_covariance_cons_variance_xyz)
        self.cons_variance_rpy = np.array(config.vist_task_covariance_cons_variance_rpy)

        # 2.5 圆柱形门控参数
        self.z_activation_threshold = config.vist_gating_z_activation_threshold
        self.dir_epsilon = config.vist_gating_dir_epsilon

        # 2.6 速度感知参数
        self.velocity_noise_floor = config.vist_velocity_perception_velocity_noise_floor
        self.max_valid_velocity = config.vist_velocity_perception_max_valid_velocity

        # 2.7 系统参数
        self.process_noise_epsilon = config.vist_filter_system_process_noise_epsilon

        # 2.8 初始化参数
        self.initial_state_variance = config.vist_initial_state_variance
        self.initial_velocity_variance = config.vist_initial_velocity_variance

        # ==========================================
        # 3. 初始化状态向量和协方差
        # ==========================================
        self.state = np.zeros(self.state_dim)  # [θ, θ̇]
        self.P = np.eye(self.state_dim)  # 状态协方差矩阵

        # 初始化协方差
        self.P[:self.n_joints, :self.n_joints] *= self.initial_state_variance
        self.P[self.n_joints:, self.n_joints:] *= self.initial_velocity_variance

        # ==========================================
        # 4. 构建状态转移矩阵 F（恒速模型）
        # ==========================================
        # F = [I  dt*I]
        #     [0   I  ]
        self.F = np.eye(self.state_dim)
        self.F[:self.n_joints, self.n_joints:] = self.dt * np.eye(self.n_joints)

        # ==========================================
        # 5. 构建观测矩阵 H
        # ==========================================
        # 观测向量 z = [q_human, q_virtual]^T (14维)
        # H = [I  0]  (人类指令：直接观测关节位置)
        #     [I  0]  (虚拟引导：微分IK转换到关节空间)
        self.H = np.zeros((2 * self.n_joints, self.state_dim))
        self.H[:self.n_joints, :self.n_joints] = np.eye(self.n_joints)
        self.H[self.n_joints:, :self.n_joints] = np.eye(self.n_joints)

        # ==========================================
        # 6. 意图检测状态
        # ==========================================
        self.alpha = 0.0  # 意图因子 (0=自由移动, 1=精密操作)
        self.alpha_smoothed = 0.0  # 平滑后的意图因子
        self.alpha_geo = 0.0  # 几何势能因子
        self.alpha_vel = 1.0  # 速度因子（初始化为1.0，表示静止状态）
        self.alpha_dir = 0.0  # 方向对齐因子
        self.alpha_vel_filter_coeff = 0.9  # 速度因子一阶低通滤波系数（0.9表示强平滑）

        # ==========================================
        # 7. 历史数据
        # ==========================================
        self.previous_shadow_joints = None  # 上一帧影子关节角度（已废弃，不再用于速度计算）
        self.previous_target_pose = None  # 上一帧目标位姿
        self.filtered_joint_vel = None  # 低通滤波后的关节速度（已废弃）
        self.velocity_filter_alpha = 0.3  # 速度滤波系数（已废弃）

        # ✅ 修复问题2: 时序逻辑 - 记录上一次更新时间
        self.last_update_time = None  # 上一次update调用的时间戳

        # 🔧 第一帧同步标志
        self._is_first_frame = True  # 标记是否是第一帧

        # ==========================================
        # 8. 统计和调试信息
        # ==========================================
        self.iteration_count = 0
        self.last_alpha_print_time = time.time()
        self.alpha_print_interval = 5.0  # 每5秒打印一次（降低频率，避免阻塞主循环）

        # 保存位姿用于 error_distance 计算
        self._last_current_pose = None
        self._last_target_pose = None

        # 保存协方差和增益范数（用于监控和日志）
        self.Q_norm = 0.0  # 过程噪声协方差范数
        self.R_norm = 0.0  # 观测噪声协方差范数
        self.K_norm = 0.0  # 卡尔曼增益范数

        # ⚠️ 性能优化：缓存运动学计算结果，避免重复 FK
        self._cached_q = None
        self._cached_pose = None
        self._cached_jacobian = None

        # 关节角度突变检测
        self._last_joint_angles = None  # 保存上一次的关节角度
        self._jump_threshold = np.pi / 2  # 突变阈值：π/2 弧度（90度）
        self._abnormal_threshold = np.pi * 1.5  # 异常值阈值：1.5π 弧度（270度）

        # 🔬 核心监控点
        self._last_raw_input = None  # 保存上一帧原始输入（用于跳跃检测）
        self._input_jump_threshold = 0.1  # 输入跳跃阈值：0.1弧度（约5.7度）
        self._frame_time_threshold = 0.0125  # 单帧耗时阈值：12.5ms（对应80Hz）

        # 监控统计
        self._monitor_print_interval = 2.0  # 每2秒打印一次监控统计
        self._last_monitor_print_time = time.time()
        self._input_jump_count = 0
        self._matrix_nan_count = 0
        self._pinocchio_slow_count = 0
        self._frame_slow_count = 0
        self._max_input_jump = 0.0
        self._max_frame_time = 0.0
        self._max_pinocchio_time = 0.0

        # 卡尔曼增益监控
        self._last_K = None  # 保存上一帧的卡尔曼增益
        self._K_delta_norm = 0.0  # 卡尔曼增益变化量范数

        # 监控数据记录（内存缓存，退出时保存）
        self._monitor_data_buffer = []  # 缓存监控数据
        self._monitor_log_enabled = True  # 启用监控日志
        self._monitor_log_path = None

        if self._monitor_log_enabled:
            # 创建日志目录
            log_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'monitor_logs')
            os.makedirs(log_dir, exist_ok=True)

            # 创建带时间戳的日志文件路径
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = f'vist_monitor_{timestamp}.csv'
            self._monitor_log_path = os.path.join(log_dir, log_filename)
            print(f"✅ 监控数据记录已启用，退出时将保存到: {self._monitor_log_path}")

        # 数据记录
        # ⚠️ 性能优化：禁用同步 CSV 写入，避免 50-200ms 的磁盘 I/O 阻塞
        self.enable_alpha_logging = False  # 临时禁用，避免控制循环卡顿
        self.alpha_log_file = None
        self.alpha_csv_writer = None

        if self.enable_alpha_logging:
            # 创建日志目录
            log_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'alpha_logs')
            os.makedirs(log_dir, exist_ok=True)

            # 创建带时间戳的日志文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_filename = f'alpha_values_{timestamp}.csv'
            log_path = os.path.join(log_dir, log_filename)

            # 打开CSV文件并写入表头
            self.alpha_log_file = open(log_path, 'w', newline='')
            self.alpha_csv_writer = csv.writer(self.alpha_log_file)
            self.alpha_csv_writer.writerow([
                'timestamp', 'iteration', 'alpha', 'alpha_smoothed',
                'alpha_geo', 'alpha_vel', 'alpha_dir',
                'error_distance', 'velocity_magnitude'
            ])

            print(f"✅ VIST卡尔曼滤波器初始化完成，α值数据记录已启用: {log_path}")
        else:
            print(f"✅ VIST卡尔曼滤波器初始化完成（性能模式：CSV记录已禁用）")

        print(f"✅ VIST参数加载完成:")
        print(f"   - 时间步长 dt: {self.dt}s")
        print(f"   - Z轴激活阈值: {self.z_activation_threshold}m")
        print(f"   - 阻尼系数: {self.differential_ik_damping}")
        print(f"   - 约束方差 XYZ: {self.cons_variance_xyz}")
        print(f"   - 自由方差 XYZ: {self.free_variance_xyz}")
        print(f"\n🔍 关键参数验证（影响Q/R比值）:")
        print(f"   - human_base_variance (R基础): {self.human_base_variance}")
        print(f"   - virtual_min_variance (R最小): {self.virtual_min_variance}")
        print(f"   - free_variance_xyz类型: {type(self.free_variance_xyz[0])}")
        print(f"   - 预期Q_norm: ~{np.sqrt(3) * self.free_variance_xyz[0] * 25 * 0.00017:.6f}")
        print(f"   - 预期R_norm: ~{np.sqrt(7) * self.human_base_variance:.6f}\n")
    # ==========================================
    # 核心算法：Step 1 - 意图检测
    # ==========================================
    def _detect_intent(self, current_pose, target_pose, shadow_joints, virtual_joints, cached_jacobian=None):
        """
        意图检测（包含圆柱形2D距离门控）

        Args:
            current_pose: 当前末端位姿 (4x4矩阵或7D向量 [x,y,z,qx,qy,qz,qw])
            target_pose: 目标末端位姿
            shadow_joints: 影子关节角度（来自遥操臂）
            virtual_joints: 虚拟引导关节角度（保留参数，未使用）
            cached_jacobian: 缓存的雅可比矩阵（性能优化）

        Returns:
            alpha: 意图因子 ∈ [0, 1]

        Note:
            ✅ 修复问题1: 速度计算现在使用卡尔曼状态估计 self.state[7:14]
            而不是数值微分，避免了高频噪声放大问题
        """
        # 提取位置
        if hasattr(current_pose, 'translation'):
            # Pinocchio SE3 对象
            current_pos = current_pose.translation
        elif isinstance(current_pose, np.ndarray) and current_pose.shape == (4, 4):
            # 4x4 变换矩阵
            current_pos = current_pose[:3, 3]
        else:
            # 7D向量 [x,y,z,qx,qy,qz,qw]
            current_pos = current_pose[:3]

        if hasattr(target_pose, 'translation'):
            # Pinocchio SE3 对象
            target_pos = target_pose.translation
        elif isinstance(target_pose, np.ndarray) and target_pose.shape == (4, 4):
            # 4x4 变换矩阵
            target_pos = target_pose[:3, 3]
        else:
            # 7D向量 [x,y,z,qx,qy,qz,qw]
            target_pos = target_pose[:3]

        # ==========================================
        # 1. 圆柱形2D距离门控（魔改1）
        # ==========================================
        # 圆柱形门控：只在XY平面（2D）计算几何距离
        # Z轴不参与门控判断，允许在任意高度激活

        # 计算XY平面（2D）误差
        error_xy = np.array([
            target_pos[0] - current_pos[0],  # X误差
            target_pos[1] - current_pos[1]   # Y误差
        ])

        # 使用w_task的前2维作为XY权重
        weighted_error_xy = self.w_task[:2] * error_xy
        error_norm_sq = np.dot(error_xy, weighted_error_xy)

        # 几何势能（高斯形式，只基于XY距离）
        # α_geo = exp(-1/2 * (XY误差)^T * W * (XY误差))
        self.alpha_geo = np.exp(-0.5 * error_norm_sq)

        # 调试信息（首次打印）
        if not hasattr(self, '_debug_printed'):
            xy_distance = np.linalg.norm(error_xy)
            print(f"[VIST DEBUG] Current XY: [{current_pos[0]:.3f}, {current_pos[1]:.3f}], Target XY: [{target_pos[0]:.3f}, {target_pos[1]:.3f}]")
            print(f"[VIST DEBUG] XY distance: {xy_distance:.3f}m, alpha_geo: {self.alpha_geo:.3f}")
            print(f"[VIST DEBUG] Current Z: {current_pos[2]:.3f}, Target Z: {target_pos[2]:.3f} (Z不参与门控)")
            self._debug_printed = True

        # ==========================================
        # 2. ✅ 修复问题1: 速度因子 α_vel - 使用卡尔曼状态估计
        # ==========================================
        # 直接使用卡尔曼滤波器状态向量中的速度估计 self.state[7:14]
        # 这是最优估计，已经融合了所有历史信息，避免了数值微分的噪声放大

        # 从状态向量提取速度估计
        joint_vel_estimate = self.state[self.n_joints:]  # 后7维是速度

        # ⚠️ 性能优化：使用缓存的雅可比矩阵，避免重复计算
        if cached_jacobian is not None:
            J = cached_jacobian[:3, :]  # 只取位置部分
        else:
            q_full = self._get_full_q_from_controlled(shadow_joints)
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

        # 末端速度（使用卡尔曼估计的关节速度）
        end_effector_vel = J @ joint_vel_estimate
        velocity_magnitude = np.linalg.norm(end_effector_vel)

        # 应用速度噪声底限
        if velocity_magnitude < self.velocity_noise_floor:
            velocity_magnitude = 0.0

        # 计算瞬时速度因子
        instant_alpha_vel = 1.0 / (1.0 + self.alpha_beta * velocity_magnitude**2)

        # ✅ 一阶低通滤波：平滑速度因子，避免剧烈跳变
        # alpha_vel(k) = λ * alpha_vel(k-1) + (1-λ) * instant_alpha_vel(k)
        # λ = 0.9 表示强平滑，响应较慢但稳定
        self.alpha_vel = self.alpha_vel_filter_coeff * self.alpha_vel + \
                         (1.0 - self.alpha_vel_filter_coeff) * instant_alpha_vel

        # ==========================================
        # 3. 方向对齐因子 α_dir
        # ==========================================
        # 计算运动方向与目标方向的余弦相似度
        if self.previous_target_pose is not None:
            # 提取上一帧目标位置
            if hasattr(self.previous_target_pose, 'translation'):
                prev_target_pos = self.previous_target_pose.translation
            elif isinstance(self.previous_target_pose, np.ndarray) and self.previous_target_pose.shape == (4, 4):
                prev_target_pos = self.previous_target_pose[:3, 3]
            else:
                prev_target_pos = self.previous_target_pose[:3]

            target_direction = target_pos - prev_target_pos
            target_dir_norm = np.linalg.norm(target_direction)

            # 当前运动方向
            current_direction = current_pos - prev_target_pos
            current_dir_norm = np.linalg.norm(current_direction)

            if target_dir_norm > self.dir_epsilon and current_dir_norm > self.dir_epsilon:
                # 归一化
                target_direction /= target_dir_norm
                current_direction /= current_dir_norm

                # 余弦相似度
                cos_theta = np.dot(target_direction, current_direction)
                cos_theta = np.clip(cos_theta, -1.0, 1.0)

                # α_dir = 1/2(1 + cos(θ))
                self.alpha_dir = 0.5 * (1.0 + cos_theta)
            else:
                self.alpha_dir = 1.0  # 静止时默认对齐
        else:
            self.alpha_dir = 1.0  # 第一帧默认对齐

        # ==========================================
        # 4. 意图因子融合
        # ==========================================
        # α_k = σ(w_g·α_geo + w_v·α_vel) · (α_dir)^η
        # 先计算加权和
        alpha_weighted = self.w_geo * self.alpha_geo + self.w_vel * self.alpha_vel

        # Sigmoid归一化
        alpha_sigmoid = 1.0 / (1.0 + np.exp(-10.0 * (alpha_weighted - 0.5)))

        # 乘以方向对齐因子（带指数）
        alpha_raw = alpha_sigmoid * (self.alpha_dir ** self.alpha_alignment_power)

        # ==========================================
        # 5. 意图平滑
        # ==========================================
        self.alpha = (1.0 - self.intent_smoothing) * alpha_raw + self.intent_smoothing * self.alpha_smoothed
        self.alpha_smoothed = self.alpha

        # 更新历史数据
        # ✅ 修复问题1: 不再需要保存 previous_shadow_joints（已使用卡尔曼状态估计）
        self.previous_target_pose = target_pose

        return self.alpha

    # ==========================================
    # 核心算法：Step 2 - 观测噪声整形
    # ==========================================
    def _shape_observation_noise(self, alpha, conflict=0.0):
        """
        观测噪声整形（动态R矩阵调度）

        Args:
            alpha: 意图因子 ∈ [0, 1]
            conflict: 冲突度量（可选）

        Returns:
            R_human: 人类指令观测噪声协方差矩阵
            R_virtual: 虚拟引导观测噪声协方差矩阵
        """
        # ==========================================
        # 1. 人类指令噪声：R_human(α) = R_min/(α + ε) + γ_c × conflict
        # ==========================================
        # 当α→0（粗略操作）时，噪声减小，增加人类指令权重
        epsilon = 1e-4  # 防止除零
        R_human_scalar = self.virtual_min_variance / (alpha + epsilon) + self.conflict_gain * conflict
        R_human = R_human_scalar * np.eye(self.n_joints)

        # ==========================================
        # 2. 虚拟引导噪声：R_virtual(α) = R_base × exp(λα)
        # ==========================================
        # 当α→1（精密操作）时，噪声减小，增加虚拟引导权重
        # 当α→0（粗略操作）时，噪声增大，降低虚拟引导权重
        R_virtual_scalar = self.human_base_variance * np.exp(self.human_lambda * alpha)
        R_virtual = R_virtual_scalar * np.eye(self.n_joints)

        return R_human, R_virtual

    # ==========================================
    # 核心算法：Step 3 - 过程噪声协方差回拉（VIST的灵魂！）
    # ==========================================
    def _pullback_covariance(self, alpha, shadow_joints, cached_jacobian=None):
        """
        过程噪声协方差回拉（VIST的灵魂！）

        这是VIST产生"粘滞感"和"物理防抖"的核心机制。
        通过在任务空间构建方向性约束，然后通过雅可比回拉到关节空间。

        Args:
            alpha: 意图因子 ∈ [0, 1]
            shadow_joints: 影子关节角度（用于计算雅可比）
            cached_jacobian: 缓存的雅可比矩阵（性能优化）

        Returns:
            Q_k: 过程噪声协方差矩阵 (state_dim x state_dim)
        """
        # ==========================================
        # 1. 构建任务空间协方差 Σ_task(α)（魔改3：保留粘滞感）
        # ==========================================
        # Σ_task(α) = (1-α)*Σ_free + α*Σ_cons
        # 注意：Σ_cons 不能为0，保留横向微小正数实现粘滞感

        # 自由方差（α=0时）
        Sigma_free = np.diag(np.concatenate([self.free_variance_xyz, self.free_variance_rpy]))
        # 修改：锁死 y 方向，只在 xz 平面上移动
        #free_variance_xyz_modified = self.free_variance_xyz.copy()
        #free_variance_xyz_modified[1] = 0.0  # 锁死 y 方向
        #Sigma_free = np.diag(np.concatenate([free_variance_xyz_modified, self.free_variance_rpy]))

        # 约束方差（α=1时，保留粘滞感）
        Sigma_cons = np.diag(np.concatenate([self.cons_variance_xyz, self.cons_variance_rpy]))
        # 修改：锁死 y 方向，只在 xz 平面上移动
        #cons_variance_xyz_modified = self.cons_variance_xyz.copy()
        #cons_variance_xyz_modified[1] = 0.0  # 锁死 y 方向
        #Sigma_cons = np.diag(np.concatenate([cons_variance_xyz_modified, self.cons_variance_rpy]))

        # 线性插值
        Sigma_task = (1.0 - alpha) * Sigma_free + alpha * Sigma_cons

        # ==========================================
        # 2. 计算雅可比矩阵（魔改2：使用固定阻尼最小二乘法）
        # ==========================================
        # ⚠️ 性能优化：使用缓存的雅可比矩阵，避免重复计算
        if cached_jacobian is not None:
            J = cached_jacobian
        else:
            q_full = self._get_full_q_from_controlled(shadow_joints)

            try:
                pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
                pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

                # 计算完整雅可比矩阵（6×n_joints：位置+姿态）
                J_full = pin.computeFrameJacobian(
                    self.ik_solver.model,
                    self.ik_solver.data,
                    q_full,
                    self.ik_solver.ee_frame_id,
                    pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
                )

                # 只使用受控关节
                J = J_full[:, self.ik_solver.controlled_indices]  # 6×n_joints
            except Exception as e:
                print(f"⚠️ [VIST] 雅可比计算失败: {e}")
                # 回退到各向同性协方差
                Sigma_vel = np.eye(self.n_joints) * 1e-3
                Q_k = np.zeros((self.state_dim, self.state_dim))
                Q_k[:self.n_joints, :self.n_joints] = (self.dt**3 / 3.0) * Sigma_vel
                Q_k[:self.n_joints, self.n_joints:] = (self.dt**2 / 2.0) * Sigma_vel
                Q_k[self.n_joints:, :self.n_joints] = (self.dt**2 / 2.0) * Sigma_vel
                Q_k[self.n_joints:, self.n_joints:] = self.dt * Sigma_vel
                Q_k += self.process_noise_epsilon * np.eye(self.state_dim)
                return Q_k

        # 如果不使用姿态控制，只取位置部分
        try:
            if not self.use_orientation_control:
                J = J[:3, :]  # 3×n_joints
                Sigma_task = Sigma_task[:3, :3]  # 3×3

                # ==========================================
                # 3. 固定阻尼最小二乘法（DLS）（魔改2）
                # ==========================================
                # J_dls = J^T (J J^T + λ² I)^(-1)
                # 这解决了奇异点崩溃并提供天然的物理粘滞感
                task_dim = J.shape[0]  # 3 或 6
                damping_sq = self.differential_ik_damping ** 2
                J_dls = J.T @ inv(J @ J.T + damping_sq * np.eye(task_dim))

                # ==========================================
                # 4. 协方差回拉到关节空间（论文公式9）
                # ==========================================
                # Σ_vel(α) = J_dls * Σ_task(α) * J_dls^T
                Sigma_vel = J_dls @ Sigma_task @ J_dls.T  # n_joints × n_joints

        except Exception as e:
            print(f"⚠️ [VIST] 协方差回拉失败: {e}")
            # 回退到各向同性协方差
            Sigma_vel = np.eye(self.n_joints) * 1e-3

        # ==========================================
        # 5. 离散化过程噪声（论文公式10）
        # ==========================================
        # Q_k(α) = [Δt³/3·Σ_vel   Δt²/2·Σ_vel]
        #          [Δt²/2·Σ_vel   Δt·Σ_vel  ]
        Q_k = np.zeros((self.state_dim, self.state_dim))

        # 位置-位置块（左上）
        Q_k[:self.n_joints, :self.n_joints] = (self.dt**3 / 3.0) * Sigma_vel

        # 位置-速度块（右上）
        Q_k[:self.n_joints, self.n_joints:] = (self.dt**2 / 2.0) * Sigma_vel

        # 速度-位置块（左下，对称）
        Q_k[self.n_joints:, :self.n_joints] = (self.dt**2 / 2.0) * Sigma_vel

        # 速度-速度块（右下）
        Q_k[self.n_joints:, self.n_joints:] = self.dt * Sigma_vel

        # ==========================================
        # 6. 添加过程噪声兜底（防止协方差退化）
        # ==========================================
        Q_k += self.process_noise_epsilon * np.eye(self.state_dim)

        return Q_k

    # ==========================================
    # 核心算法：Step 4 - 卡尔曼滤波更新
    # ==========================================
    def update(self, shadow_joints, target_pose, virtual_joints=None):
        """
        VIST卡尔曼滤波器主更新函数

        Args:
            shadow_joints: 影子关节角度（来自遥操臂，纯前馈输入）
            target_pose: 目标末端位姿（用于意图检测）
            virtual_joints: 虚拟引导关节角度（微分IK输出，可选）

        Returns:
            filtered_joints: 滤波后的关节角度
        """
        # ==========================================
        # 🔬 监控点1: 单帧执行耗时监控
        # ==========================================
        frame_start_time = time.time()

        self.iteration_count += 1

        # ==========================================
        # 🔬 监控点2: 原始输入跳跃监控
        # ==========================================
        # 检测遥操臂传来的相邻两帧数据差值
        # 如果单帧差值超过0.1弧度（约5.7度），说明可能是通信丢包或数据解析归零
        shadow_joints_array = np.array(shadow_joints)
        max_jump = 0.0
        if self._last_raw_input is not None:
            input_delta = shadow_joints_array - self._last_raw_input
            max_jump = np.max(np.abs(input_delta))
            if max_jump > self._input_jump_threshold:
                jump_joint_idx = np.argmax(np.abs(input_delta))
                print(f"🚨 [VIST监控] 原始输入跳跃检测: Joint {jump_joint_idx} 跳变 {max_jump:.4f} rad ({np.rad2deg(max_jump):.2f}°)")
                print(f"   上一帧: {self._last_raw_input[jump_joint_idx]:.4f}, 当前帧: {shadow_joints_array[jump_joint_idx]:.4f}")
                self._input_jump_count += 1
            # 更新最大跳变记录
            if max_jump > self._max_input_jump:
                self._max_input_jump = max_jump
        self._last_raw_input = shadow_joints_array.copy()

        # ==========================================
        # 🔬 死锁测试模式（诊断用）
        # ==========================================
        # 用于诊断抖动来源：外部输入 vs 算法内部
        #
        # 测试方法：
        # 1. 强制 α=1.0（全约束模式）
        # 2. 强制观测值=当前状态（不接受外部输入）
        # 3. 系统变成"自己跟自己玩"
        #
        # 诊断结果：
        # - 如果不抖了：抖动来自外部输入（遥操臂信号脏）或α跳变
        # - 如果还在抖：算法内部增益过大，自激震荡
        #
        # ⚠️ 使用方法：取消下面3行的注释，重启节点测试
        ENABLE_DEADLOCK_TEST = True
        if ENABLE_DEADLOCK_TEST:
            alpha = 0  # 锁定为全约束模式
            shadow_joints = self.state[:self.n_joints]  # 观测值=当前状态
            print(f"[DEADLOCK TEST] α={alpha:.3f}, using internal state as observation")
            # 跳过意图检测，直接使用锁定的alpha
            self.alpha = alpha
            self.alpha_smoothed = alpha

        # ==========================================
        # Step 0.0: 角度归一化 - 将输入角度限制在 [-π/2, +π/2]内容
        # ==========================================
        # 防止角度突变（例如从 -π 跳到 +π）
        shadow_joints = self._normalize_joint_angles(shadow_joints, label="input_shadow")
        if virtual_joints is not None:
            virtual_joints = self._normalize_joint_angles(virtual_joints, label="input_virtual")

        # ==========================================
        # 🔧 第一帧同步：将卡尔曼状态初始化为遥操臂当前状态
        # ==========================================
        if self._is_first_frame:
            print(f"[VIST] 第一帧同步遥操臂状态:")
            print(f"  初始状态（零向量）: {self.state[:self.n_joints]}")
            print(f"  遥操臂状态: {shadow_joints}")

            # 将位置状态设置为遥操臂当前角度
            self.state[:self.n_joints] = shadow_joints.copy()
            # 速度状态保持为零（假设初始静止）
            self.state[self.n_joints:] = 0.0

            print(f"  同步后状态: {self.state[:self.n_joints]}")
            print(f"[VIST] 第一帧同步完成\n")

            self._is_first_frame = False

        # ==========================================
        # Step 0.1: ✅ 修复问题2 - 动态更新F矩阵
        # ==========================================
        # 计算实际流逝时间，而不是使用固定dt
        current_time = time.time()
        if self.last_update_time is not None:
            actual_dt = current_time - self.last_update_time
            # 限制dt范围，避免异常值
            if 0.001 < actual_dt < 0.1:  # 10Hz到1000Hz之间
                # 动态更新F矩阵
                self.F[:self.n_joints, self.n_joints:] = actual_dt * np.eye(self.n_joints)
            else:
                # 异常值，使用配置的dt
                actual_dt = self.dt
        else:
            # 第一次调用，使用配置的dt
            actual_dt = self.dt

        self.last_update_time = current_time

        # ==========================================
        # Step 0.2: 计算当前末端位姿（使用缓存，避免重复计算）
        # ==========================================
        # ⚠️ 性能优化：只计算一次 FK 和雅可比，后续复用
        current_pose, cached_jacobian = self._compute_kinematics_once(shadow_joints)

        # ✅ 保存位姿用于 error_distance 计算
        self._last_current_pose = current_pose
        self._last_target_pose = target_pose

        # ==========================================
        # Step 1: 意图检测（传入缓存的雅可比）
        # ==========================================
        # 如果启用死锁测试，跳过意图检测，使用固定alpha
        if not ENABLE_DEADLOCK_TEST:
            alpha = self._detect_intent(current_pose, target_pose, shadow_joints, virtual_joints, cached_jacobian)

        # ✅ 明确使用平滑后的alpha驱动协方差
        # _detect_intent已经对alpha进行了平滑处理（第375-376行）
        # 这里使用self.alpha_smoothed确保所有协方差调度都基于平滑后的意图因子
        alpha_for_covariance = self.alpha_smoothed

        # ==========================================
        # Step 2: 观测噪声整形
        # ==========================================
        R_human, R_virtual = self._shape_observation_noise(alpha_for_covariance)

        # ==========================================
        # Step 3: 过程噪声协方差回拉（传入缓存的雅可比）
        # ==========================================
        Q_k = self._pullback_covariance(alpha_for_covariance, shadow_joints, cached_jacobian)

        # ==========================================
        # Step 4: 卡尔曼滤波预测步骤
        # ==========================================
        # 保存当前状态（用于计算预测位移）
        state_before_prediction = self.state[:self.n_joints].copy()

        # 状态预测：x̂_{k|k-1} = F * x̂_{k-1}
        x_pred = self.F @ self.state

        # 计算预测位移（关节空间）
        prediction_displacement = x_pred[:self.n_joints] - state_before_prediction

        # 协方差预测：P_{k|k-1} = F * P_{k-1} * F^T + Q_k
        P_pred = self.F @ self.P @ self.F.T + Q_k

        # ==========================================
        # Step 5: 构建观测向量
        # ==========================================
        # 观测向量 z = [q_human, q_virtual]^T
        if virtual_joints is not None:
            z = np.concatenate([shadow_joints, virtual_joints])
        else:
            # 如果没有虚拟引导，使用影子关节作为虚拟引导
            z = np.concatenate([shadow_joints, shadow_joints])

        # ==========================================
        # Step 6: 构建观测噪声协方差矩阵
        # ==========================================
        # 根据融合方法选择
        if self.fusion_method == "information":
            # ⚠️ 性能优化：对角矩阵求逆使用 O(N) 算法，避免 O(N³) 的通用求逆
            # R_human 和 R_virtual 都是对角矩阵，直接对对角元素求倒数
            R_human_diag = np.diag(R_human)
            R_virtual_diag = np.diag(R_virtual)

            # inv(R_human) + inv(R_virtual) 的对角元素
            inv_sum_diag = 1.0 / R_human_diag + 1.0 / R_virtual_diag

            # R_eff = inv(inv_sum) 的对角元素
            R_eff_diag = 1.0 / inv_sum_diag
            R_eff = np.diag(R_eff_diag)

            # 合成观测（利用对角性质）
            z_syn = R_eff_diag * (z[:self.n_joints] / R_human_diag + z[self.n_joints:] / R_virtual_diag)

            # 使用单一观测矩阵
            H_eff = self.H[:self.n_joints, :]
        else:
            # 标准卡尔曼滤波：观测向量堆叠
            R_eff = np.block([
                [R_human, np.zeros((self.n_joints, self.n_joints))],
                [np.zeros((self.n_joints, self.n_joints)), R_virtual]
            ])
            z_syn = z
            H_eff = self.H

        # ==========================================
        # Step 7: 卡尔曼增益计算
        # ==========================================
        # S = H * P_{k|k-1} * H^T + R_eff
        S = H_eff @ P_pred @ H_eff.T + R_eff

        # K_k = P_{k|k-1} * H^T * S^{-1}
        K = P_pred @ H_eff.T @ inv(S)

        # 保存协方差和增益范数（用于监控）
        self.Q_norm = np.linalg.norm(Q_k, 'fro')  # Frobenius范数
        self.R_norm = np.linalg.norm(R_eff, 'fro')
        self.K_norm = np.linalg.norm(K, 'fro')

        # 计算卡尔曼增益变化量
        if self._last_K is not None:
            K_delta = K - self._last_K
            self._K_delta_norm = np.linalg.norm(K_delta, 'fro')
        else:
            self._K_delta_norm = 0.0
        self._last_K = K.copy()

        # ==========================================
        # 🔬 监控点3: 矩阵数值崩溃监控
        # ==========================================
        # 检测卡尔曼增益 K 和状态向量是否出现 NaN 或 Inf
        if np.any(np.isnan(K)) or np.any(np.isinf(K)):
            print(f"🚨 [VIST监控] 卡尔曼增益矩阵崩溃: 检测到 NaN 或 Inf")
            print(f"   K_norm: {self.K_norm:.6f}")
            print(f"   S condition number: {np.linalg.cond(S):.2e}")
            self._matrix_nan_count += 1

        if np.any(np.isnan(P_pred)) or np.any(np.isinf(P_pred)):
            print(f"🚨 [VIST监控] 预测协方差矩阵崩溃: 检测到 NaN 或 Inf")
            print(f"   P_pred condition number: {np.linalg.cond(P_pred):.2e}")
            self._matrix_nan_count += 1

        # ==========================================
        # Step 8: 状态更新
        # ==========================================
        # 创新（innovation）：y = z_syn - H * x̂_{k|k-1}
        innovation = z_syn - H_eff @ x_pred

        # 计算卡尔曼修正量：K_k * y
        kalman_correction = K @ innovation

        # 状态更新：x̂_k = x̂_{k|k-1} + K_k * y
        self.state = x_pred + kalman_correction

        # 角度归一化：将状态向量中的关节角度限制在 [-π, +π]
        self.state[:self.n_joints] = self._normalize_joint_angles(self.state[:self.n_joints], label="state_update")

        # ==========================================
        # 🔬 监控点3续: 状态向量数值崩溃监控
        # ==========================================
        if np.any(np.isnan(self.state)) or np.any(np.isinf(self.state)):
            print(f"🚨 [VIST监控] 状态向量崩溃: 检测到 NaN 或 Inf")
            print(f"   State: {self.state[:self.n_joints]}")
            self._matrix_nan_count += 1

        # 协方差更新：P_k = (I - K_k * H) * P_{k|k-1}
        I = np.eye(self.state_dim)
        self.P = (I - K @ H_eff) @ P_pred

        # ==========================================
        # Step 9: 提取滤波后的关节角度
        # ==========================================
        filtered_joints = self.state[:self.n_joints].copy()

        # 输出角度归一化：确保输出也在 [-π, +π] 范围内
        filtered_joints = self._normalize_joint_angles(filtered_joints, label="output")

        # 计算输入输出差异（验证滤波是否工作）
        input_output_diff = np.linalg.norm(filtered_joints - shadow_joints)

        # ==========================================
        # Step 10: 数据记录和调试输出
        # ==========================================
        self._log_alpha_data(R_human, R_virtual, Q_k, K, innovation, input_output_diff)

        # ==========================================
        # 🔬 监控点4: 单帧执行耗时监控
        # ==========================================
        frame_end_time = time.time()
        frame_duration = frame_end_time - frame_start_time

        # 更新最大耗时记录
        if frame_duration > self._max_frame_time:
            self._max_frame_time = frame_duration

        if frame_duration > self._frame_time_threshold:
            print(f"🚨 [VIST监控] 单帧执行耗时超标: {frame_duration*1000:.2f}ms (阈值: {self._frame_time_threshold*1000:.2f}ms)")
            print(f"   对应频率: {1.0/frame_duration:.1f}Hz (目标: 80Hz)")
            self._frame_slow_count += 1

        # ==========================================
        # 🔬 记录监控数据到内存缓存
        # ==========================================
        if self._monitor_log_enabled:
            # 计算关键量的范数
            prediction_disp_norm = np.linalg.norm(prediction_displacement)
            innovation_norm = np.linalg.norm(innovation[:self.n_joints])  # 只取关节部分
            correction_norm = np.linalg.norm(kalman_correction[:self.n_joints])  # 只取关节部分

            monitor_record = {
                'timestamp': time.time(),
                'iteration': self.iteration_count,
                'frame_duration_ms': frame_duration * 1000,
                'frame_frequency_hz': 1.0 / frame_duration if frame_duration > 0 else 0,
                'K_norm': self.K_norm,
                'K_delta_norm': self._K_delta_norm,
                'Q_norm': self.Q_norm,
                'R_norm': self.R_norm,
                'input_jump': max_jump if 'max_jump' in locals() else 0.0,
                'pinocchio_time_ms': self._max_pinocchio_time * 1000,
                'alpha': self.alpha_smoothed,
                'prediction_displacement_norm': prediction_disp_norm,
                'innovation_norm': innovation_norm,
                'correction_norm': correction_norm,
            }
            self._monitor_data_buffer.append(monitor_record)

        # ==========================================
        # 🔬 定期打印监控统计
        # ==========================================
        current_time = time.time()
        if current_time - self._last_monitor_print_time >= self._monitor_print_interval:
            # 计算当前帧的卡尔曼滤波关键量（用于打印）
            if self._monitor_log_enabled and len(self._monitor_data_buffer) > 0:
                latest = self._monitor_data_buffer[-1]
                pred_disp = latest['prediction_displacement_norm']
                innov = latest['innovation_norm']
                corr = latest['correction_norm']
            else:
                pred_disp = innov = corr = 0.0

            print(f"\n📊 [VIST监控统计] (过去 {self._monitor_print_interval:.1f}s)")
            print(f"   输入跳跃: {self._input_jump_count} 次, 最大跳变: {self._max_input_jump:.4f} rad ({np.rad2deg(self._max_input_jump):.2f}°)")
            print(f"   矩阵崩溃: {self._matrix_nan_count} 次")
            print(f"   Pinocchio慢: {self._pinocchio_slow_count} 次, 最大耗时: {self._max_pinocchio_time*1000:.2f}ms")
            print(f"   单帧慢: {self._frame_slow_count} 次, 最大耗时: {self._max_frame_time*1000:.2f}ms ({1.0/self._max_frame_time:.1f}Hz)")
            print(f"   当前帧耗时: {frame_duration*1000:.2f}ms ({1.0/frame_duration:.1f}Hz)")
            print(f"   📈 卡尔曼增益: K_norm={self.K_norm:.6f}, ΔK_norm={self._K_delta_norm:.6f}")
            print(f"   📐 卡尔曼滤波: 预测位移={pred_disp:.6f}, 创新={innov:.6f}, 修正={corr:.6f}")
            print(f"   Q_norm: {self.Q_norm:.4f}, R_norm: {self.R_norm:.4f}\n")

            # 重置统计
            self._last_monitor_print_time = current_time
            self._input_jump_count = 0
            self._matrix_nan_count = 0
            self._pinocchio_slow_count = 0
            self._frame_slow_count = 0
            self._max_input_jump = 0.0
            self._max_frame_time = 0.0
            self._max_pinocchio_time = 0.0

        return filtered_joints

    # ==========================================
    # 辅助函数
    # ==========================================
    def _normalize_angle(self, angle):
        """
        将角度归一化到 [-π/2, +π/2] 范围内，防止突变

        Args:
            angle: 输入角度（弧度）

        Returns:
            归一化后的角度（弧度），范围 [-π/2, +π/2]
        """
        # 先归一化到 [-π, +π]
        angle_normalized = np.arctan2(np.sin(angle), np.cos(angle))

        # 再限制到 [-π/2, +π/2]
        if angle_normalized > np.pi / 2:
            angle_normalized = np.pi / 2
        elif angle_normalized < -np.pi / 2:
            angle_normalized = -np.pi / 2

        return angle_normalized

    def _normalize_joint_angles(self, q, label=""):
        """
        将关节角度向量归一化到 [-π/2, +π/2] 范围内

        Args:
            q: 关节角度向量（弧度）
            label: 标签，用于标识数据来源（保留参数，不再使用）

        Returns:
            归一化后的关节角度向量
        """
        q_normalized = np.array([self._normalize_angle(qi) for qi in q])

        # 更新历史记录（用于其他监控）
        self._last_joint_angles = q_normalized.copy()

        return q_normalized

    def _get_full_q_from_controlled(self, q_controlled):
        """
        从受控关节角度构建完整的关节角度向量

        Args:
            q_controlled: 受控关节角度（n_joints维）

        Returns:
            q_full: 完整关节角度（包含未受控关节）
        """
        q_full = np.zeros(self.ik_solver.model.nq)
        q_full[self.ik_solver.controlled_indices] = q_controlled
        return q_full

    def _compute_kinematics_once(self, shadow_joints):
        """
        ⚠️ 性能优化：只计算一次运动学，缓存结果

        避免在单次 update() 中重复计算 FK 和雅可比（原本 4 次 → 1 次）
        节省 2-8ms 的计算时间

        Args:
            shadow_joints: 影子关节角度

        Returns:
            pose: 末端位姿
            jacobian: 雅可比矩阵（只包含受控关节）
        """
        # 检查缓存是否有效
        if self._cached_q is not None and np.allclose(self._cached_q, shadow_joints):
            return self._cached_pose, self._cached_jacobian

        # ==========================================
        # 🔬 监控点5: Pinocchio计算耗时监控
        # ==========================================
        pinocchio_start_time = time.time()

        # 计算正向运动学
        q_full = self._get_full_q_from_controlled(shadow_joints)
        fk_start = time.time()
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_full)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)
        fk_duration = time.time() - fk_start

        pose = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id]

        # 计算雅可比矩阵
        jacobian_start = time.time()
        J_full = pin.computeFrameJacobian(
            self.ik_solver.model,
            self.ik_solver.data,
            q_full,
            self.ik_solver.ee_frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )
        jacobian = J_full[:, self.ik_solver.controlled_indices]
        jacobian_duration = time.time() - jacobian_start

        pinocchio_total_duration = time.time() - pinocchio_start_time

        # 更新最大耗时记录
        if pinocchio_total_duration > self._max_pinocchio_time:
            self._max_pinocchio_time = pinocchio_total_duration

        # 监控：如果Pinocchio计算耗时超过5ms，打印警告
        if pinocchio_total_duration > 0.005:
            print(f"🚨 [VIST监控] Pinocchio计算耗时超标: {pinocchio_total_duration*1000:.2f}ms")
            print(f"   FK耗时: {fk_duration*1000:.2f}ms, Jacobian耗时: {jacobian_duration*1000:.2f}ms")
            self._pinocchio_slow_count += 1

        # 缓存结果
        self._cached_q = shadow_joints.copy()
        self._cached_pose = pose
        self._cached_jacobian = jacobian

        return pose, jacobian

    def _log_alpha_data(self, R_human=None, R_virtual=None, Q_k=None, K=None, innovation=None, input_output_diff=None):
        """记录α值数据到CSV文件，并打印噪声矩阵信息"""

        # ✅ 计算真实的 error_distance（使用欧式距离）
        if self._last_current_pose is not None and self._last_target_pose is not None:
            # 提取位置
            if hasattr(self._last_current_pose, 'translation'):
                current_pos = self._last_current_pose.translation
            elif isinstance(self._last_current_pose, np.ndarray) and self._last_current_pose.shape == (4, 4):
                current_pos = self._last_current_pose[:3, 3]
            else:
                current_pos = self._last_current_pose[:3]

            if hasattr(self._last_target_pose, 'translation'):
                target_pos = self._last_target_pose.translation
            elif isinstance(self._last_target_pose, np.ndarray) and self._last_target_pose.shape == (4, 4):
                target_pos = self._last_target_pose[:3, 3]
            else:
                target_pos = self._last_target_pose[:3]

            # 计算 3D 欧氏距离
            error_distance = np.linalg.norm(target_pos - current_pos)
        else:
            error_distance = 0.0

        # ✅ 计算真实的 velocity_magnitude
        if hasattr(self, 'filtered_joint_vel') and self.filtered_joint_vel is not None:
            # 通过雅可比转换到末端速度
            try:
                q_full = self._get_full_q_from_controlled(self.state[:self.n_joints])
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
                end_effector_vel = J @ self.filtered_joint_vel
                velocity_magnitude = np.linalg.norm(end_effector_vel)
            except Exception as e:
                velocity_magnitude = 0.0
        else:
            velocity_magnitude = 0.0

        if self.enable_alpha_logging and self.alpha_csv_writer is not None:
            self.alpha_csv_writer.writerow([
                time.time(),
                self.iteration_count,
                self.alpha,
                self.alpha_smoothed,
                self.alpha_geo,
                self.alpha_vel,
                self.alpha_dir,
                error_distance,      # ✅ 真实值
                velocity_magnitude   # ✅ 真实值
            ])

        # 定期打印α值和噪声矩阵
        current_time = time.time()
        if current_time - self.last_alpha_print_time > self.alpha_print_interval:
            # 打印意图因子
            print(f"[VIST] α={self.alpha:.3f} (geo={self.alpha_geo:.3f}, vel={self.alpha_vel:.3f}, dir={self.alpha_dir:.3f})")

            # 打印输入输出差异（验证滤波是否工作）
            if input_output_diff is not None:
                print(f"[VIST] 输入输出差异 ||filtered - input||={input_output_diff:.6f} rad")

            # 打印噪声矩阵信息
            if R_human is not None and R_virtual is not None:
                # 取对角线元素的平均值作为代表
                r_human_avg = np.mean(np.diag(R_human))
                r_virtual_avg = np.mean(np.diag(R_virtual))
                print(f"[VIST] 观测噪声 R_human={r_human_avg:.6f}, R_virtual={r_virtual_avg:.6f}")

            if Q_k is not None:
                # 取位置块的对角线平均值
                q_pos_avg = np.mean(np.diag(Q_k[:self.n_joints, :self.n_joints]))
                q_vel_avg = np.mean(np.diag(Q_k[self.n_joints:, self.n_joints:]))
                print(f"[VIST] 过程噪声 Q_pos={q_pos_avg:.6f}, Q_vel={q_vel_avg:.6f}")

            if K is not None:
                # 打印卡尔曼增益的范数
                k_norm = np.linalg.norm(K)
                print(f"[VIST] 卡尔曼增益范数 ||K||={k_norm:.6f}")

            if innovation is not None:
                # 打印创新向量的范数
                innov_norm = np.linalg.norm(innovation)
                print(f"[VIST] 创新向量范数 ||innovation||={innov_norm:.6f}")

            print("")  # 空行分隔
            self.last_alpha_print_time = current_time

    def get_velocity_estimate(self):
        """
        获取速度估计（用于外部模块）

        Returns:
            velocity: 关节速度估计（n_joints维）
        """
        return self.state[self.n_joints:]

    def get_intent_factor(self):
        """
        获取当前意图因子

        Returns:
            alpha: 意图因子 ∈ [0, 1]
        """
        return self.alpha_smoothed

    def reset(self, initial_joints=None):
        """
        重置滤波器状态

        Args:
            initial_joints: 初始关节角度（可选）
        """
        if initial_joints is not None:
            self.state[:self.n_joints] = initial_joints
        else:
            self.state = np.zeros(self.state_dim)

        # 重置协方差
        self.P = np.eye(self.state_dim)
        self.P[:self.n_joints, :self.n_joints] *= self.initial_state_variance
        self.P[self.n_joints:, self.n_joints:] *= self.initial_velocity_variance

        # 重置意图状态
        self.alpha = 0.0
        self.alpha_smoothed = 0.0
        self.alpha_geo = 0.0
        self.alpha_vel = 0.0
        self.alpha_dir = 0.0

        # 重置历史数据
        self.previous_shadow_joints = None
        self.previous_target_pose = None

        print("✅ VIST卡尔曼滤波器已重置")

    def save_monitor_data(self):
        """手动保存监控数据到CSV文件"""
        if self._monitor_log_enabled and len(self._monitor_data_buffer) > 0:
            try:
                import pandas as pd
                df = pd.DataFrame(self._monitor_data_buffer)
                df.to_csv(self._monitor_log_path, index=False)
                print(f"✅ 监控数据已保存: {self._monitor_log_path} ({len(self._monitor_data_buffer)} 条记录)")
                return True
            except Exception as e:
                print(f"⚠️ 监控数据保存失败: {e}")
                return False
        return False

    def __del__(self):
        """析构函数：关闭日志文件并保存监控数据"""
        # 保存监控数据
        if self._monitor_log_enabled and len(self._monitor_data_buffer) > 0:
            try:
                import pandas as pd
                df = pd.DataFrame(self._monitor_data_buffer)
                df.to_csv(self._monitor_log_path, index=False)
                print(f"✅ 监控数据已保存: {self._monitor_log_path} ({len(self._monitor_data_buffer)} 条记录)")
            except Exception as e:
                print(f"⚠️ 监控数据保存失败: {e}")

        # 关闭alpha日志文件
        if self.alpha_log_file is not None:
            self.alpha_log_file.close()
            print("✅ α值数据记录已保存")
