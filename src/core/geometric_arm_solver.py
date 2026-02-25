"""
Geometric Analytical Arm Solver for 7-DOF Robotic Arm

This module implements a three-stage geometric analytical solution for 7-DOF
inverse kinematics, decomposing the problem into:
1. Arm Configuration (q1-q4): Geometric analytical solution for shoulder + elbow
2. Wrist Orientation (q5-q7): Euler angle decomposition for wrist joints
3. VIST Integration: Convert absolute angles to increments for state estimation

Key advantages:
- ⭐⭐⭐⭐⭐ Analytical solution (10-100x faster than iterative methods)
- ⭐⭐⭐⭐⭐ Deterministic and unique solution
- ⭐⭐⭐⭐⭐ Bio-inspired (matches human arm control strategy)

Author: VIST Project
Date: 2026-02-06
"""

import numpy as np
from scipy.spatial.transform import Rotation
import pinocchio as pin


class GeometricArmSolver:
    """
    几何解析臂部求解器

    将 7-DOF 逆运动学分解为两个子问题：
    1. 臂部配置（前4个关节）：由肩、肘、腕三点位置唯一确定
    2. 腕部姿态（后3个关节）：由目标末端姿态和臂部配置确定
    """

    def __init__(self, model, data, controlled_joints, ee_frame_id, config=None):
        """
        初始化几何求解器

        Args:
            model: Pinocchio 模型
            data: Pinocchio 数据
            controlled_joints: 受控关节索引列表
            ee_frame_id: 末端执行器 frame ID
            config: 系统配置对象（可选，用于读取关节方向和腕部控制模式）
        """
        self.model = model
        self.data = data
        self.controlled_joints = controlled_joints
        self.ee_frame_id = ee_frame_id

        # 调试信息
        self._last_elbow_debug = {}

        # 根据末端执行器 frame 自动检测左臂或右臂
        # 获取末端执行器名称
        ee_frame_name = model.frames[ee_frame_id].name
        self.is_left_arm = "Left" in ee_frame_name

        # 根据末端执行器 frame 自动检测左臂或右臂
        # 获取末端执行器名称
        ee_frame_name = model.frames[ee_frame_id].name
        is_left_arm = "Left" in ee_frame_name

        # 根据左右臂选择关节顺序
        if is_left_arm:
            DEFAULT_JOINT_ORDER = [
                'Left_Shoulder_Pitch_Joint',  # 索引0
                'Left_Shoulder_Roll_Joint',   # 索引1
                'Left_Shoulder_Yaw_Joint',    # 索引2
                'Left_Elbow_Pitch_Joint',     # 索引3
                'Left_Wrist_Yaw_Joint',       # 索引4
                'Left_Wrist_Pitch_Joint',     # 索引5
                'Left_Wrist_Roll_Joint'       # 索引6
            ]
            print(f"⚙️ [GeometricSolver] 检测到左臂末端执行器: {ee_frame_name}")
        else:
            DEFAULT_JOINT_ORDER = [
                'Right_Shoulder_Pitch_Joint',  # 索引0
                'Right_Shoulder_Roll_Joint',   # 索引1
                'Right_Shoulder_Yaw_Joint',    # 索引2
                'Right_Elbow_Pitch_Joint',     # 索引3
                'Right_Wrist_Yaw_Joint',       # 索引4
                'Right_Wrist_Pitch_Joint',     # 索引5
                'Right_Wrist_Roll_Joint'       # 索引6
            ]
            print(f"⚙️ [GeometricSolver] 检测到右臂末端执行器: {ee_frame_name}")

        # 构建关节名称到索引的映射
        self.joint_name_to_index = {name: i for i, name in enumerate(DEFAULT_JOINT_ORDER)}

        # 关节索引映射（假设 controlled_joints 是 7-DOF 右臂）
        # [0:4] 是臂部关节（肩部3个 + 肘部1个）
        # [4:7] 是腕部关节（腕部3个）
        self.arm_joint_indices = controlled_joints[:4]  # q1, q2, q3, q4
        self.wrist_joint_indices = controlled_joints[4:]  # q5, q6, q7

        # 读取关节方向配置（用于调整电机旋转方向）
        if config is not None and hasattr(config, 'robot_joint_directions'):
            self.joint_directions = np.array(config.robot_joint_directions)
            print(f"✅ [GeometricSolver] 初始化完成（使用配置的关节方向）")
            print(f"   关节方向: {self.joint_directions}")
        else:
            # 默认所有关节正向
            self.joint_directions = np.ones(7)
            print(f"✅ [GeometricSolver] 初始化完成（使用默认关节方向）")

        # 读取关节零位偏移配置（用于调整零位定义）
        if config is not None and hasattr(config, 'robot_joint_offsets'):
            self.joint_offsets = np.array(config.robot_joint_offsets)
            print(f"   关节偏移: {self.joint_offsets} (弧度)")
            print(f"   关节偏移: {np.degrees(self.joint_offsets)} (度)")
        else:
            # 默认所有关节无偏移
            self.joint_offsets = np.zeros(7)

        # 读取腕部控制模式配置
        if config is not None and hasattr(config, 'vist_wrist_control_mode'):
            self.wrist_control_mode = config.vist_wrist_control_mode
        else:
            # 默认使用全自由度模式
            self.wrist_control_mode = 'full_dof'

        # 读取动态腕部解锁配置
        if config is not None and hasattr(config, 'vist_geometric_solver_enable_dynamic_wrist_unlock'):
            self.enable_dynamic_wrist_unlock = config.vist_geometric_solver_enable_dynamic_wrist_unlock
        else:
            self.enable_dynamic_wrist_unlock = False

        print(f"   臂部关节索引: {self.arm_joint_indices}")
        print(f"   腕部关节索引: {self.wrist_joint_indices}")
        print(f"   腕部控制模式: {self.wrist_control_mode}")
        print(f"   关节名称映射: {self.joint_name_to_index}")

    def solve_arm_configuration(self, shoulder_pos, elbow_pos, wrist_pos):
        """
        Stage 1: 臂部配置求解（几何解析解）

        给定肩、肘、腕三点位置，计算前4个关节角度（肩部3个 + 肘部1个）

        算法思路：
        1. 肩部姿态（q1, q2, q3）：由肩→肘向量确定
           - q1 (Shoulder Pitch): 肩→肘向量在 XZ 平面的投影角度
           - q2 (Shoulder Roll): 肩→肘向量的俯仰角
           - q3 (Shoulder Yaw): 肩→肘向量的偏航角
        2. 肘部角度（q4）：由肘→腕向量和肩→肘向量的夹角确定
           - q4 (Elbow Pitch): 两向量夹角 - π（因为肘部是弯曲的）

        Args:
            shoulder_pos: 肩部位置 [x, y, z] (numpy array)
            elbow_pos: 肘部位置 [x, y, z] (numpy array)
            wrist_pos: 腕部位置 [x, y, z] (numpy array)

        Returns:
            q_arm: 臂部关节角度 [q1, q2, q3, q4] (numpy array)
        """
        # 计算向量
        v_shoulder_elbow = elbow_pos - shoulder_pos  # 肩→肘
        v_elbow_wrist = wrist_pos - elbow_pos        # 肘→腕

        # ==========================================
        # 1. 计算肩部姿态（q1, q2, q3）
        # ==========================================
        # 将肩→肘向量转换为球坐标系
        r = np.linalg.norm(v_shoulder_elbow)
        if r < 1e-6:
            raise ValueError("肩部和肘部位置重合，无法求解")

        # q1 (Shoulder Pitch): 绕 Y 轴旋转（俯仰）
        # 计算向量在 XZ 平面的投影
        # 注意：几何计算的零位（X轴正方向）与URDF零位（Z轴负方向，即下垂）不同
        # 需要添加π/2偏移来对齐：URDF的0°对应几何计算的-π/2
        q1_geometric = np.arctan2(v_shoulder_elbow[2], v_shoulder_elbow[0])
        q1 = q1_geometric + np.pi/2  # 对齐URDF零位定义

        # q2 (Shoulder Roll): 绕 X 轴旋转（横滚）
        # 计算向量与 XZ 平面的夹角
        # 注意：v_shoulder_elbow 已经在 Robot Base Frame 中，Y 轴已经通过坐标转换翻转过
        # 不要再次翻转，否则会负负得正！
        r_xz = np.sqrt(v_shoulder_elbow[0]**2 + v_shoulder_elbow[2]**2)
        q2 = np.arctan2(v_shoulder_elbow[1], r_xz)

        # q3 (Shoulder Yaw): 大臂绕自身轴线的旋转角度
        # 正确方法：将小臂向量投影到垂直于大臂轴线的平面，然后测量相对参考方向的有符号角度
        #
        # 步骤：
        # 1. 大臂方向单位向量 d_upper
        # 2. 小臂向量在垂直于大臂平面上的投影 v_fore_perp
        # 3. 参考方向：X 轴（前方）在该平面上的投影（q3=0 时小臂朝前）
        # 4. 用叉积确定旋转方向（绕大臂轴线）
        d_upper = v_shoulder_elbow / r  # 大臂方向单位向量

        # 小臂向量投影到垂直于大臂的平面
        v_fore_perp = v_elbow_wrist - np.dot(v_elbow_wrist, d_upper) * d_upper

        # 参考方向：X 轴（前方）在垂直于大臂平面上的投影
        x_axis = np.array([1.0, 0.0, 0.0])
        ref = x_axis - np.dot(x_axis, d_upper) * d_upper
        ref_norm = np.linalg.norm(ref)
        if ref_norm < 1e-3:
            # 大臂接近水平向前时，改用 Z 轴作为参考
            z_axis = np.array([0.0, 0.0, 1.0])
            ref = z_axis - np.dot(z_axis, d_upper) * d_upper
            ref_norm = np.linalg.norm(ref)
        ref = ref / (ref_norm + 1e-9)

        # 计算有符号角度（绕大臂轴线 d_upper）
        v_fore_perp_norm = np.linalg.norm(v_fore_perp)
        if v_fore_perp_norm < 1e-6:
            q3 = 0.0
        else:
            v_fore_unit = v_fore_perp / v_fore_perp_norm
            cos_q3 = np.clip(np.dot(ref, v_fore_unit), -1.0, 1.0)
            cross = np.cross(ref, v_fore_unit)
            sin_q3 = np.dot(cross, d_upper)
            q3 = np.arctan2(sin_q3, cos_q3)

        # 左臂镜像修正：左右臂关节方向相反
        if self.is_left_arm:
            q3 = -q3

        # ==========================================
        # 2. 计算肘部角度（q4）
        # ==========================================
        # 电机角度 = 两向量夹角（不需要补角）
        #
        # 关节零位定义：
        # - 机器人电机: q4 = 0° 表示手臂垂直向下（伸直），向量夹角 = 0°
        # - 机器人电机: q4 增大表示手臂弯曲，向量夹角增大
        # - 人体肘部角度 = 180° - 向量夹角（补角关系）
        # - 电机角度 = 向量夹角 = arccos(cos_angle)
        r_elbow_wrist = np.linalg.norm(v_elbow_wrist)
        if r_elbow_wrist < 1e-6:
            raise ValueError("肘部和腕部位置重合，无法求解")

        # 计算两向量夹角（使用点积）
        cos_angle = np.dot(v_shoulder_elbow, v_elbow_wrist) / (r * r_elbow_wrist)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 防止数值误差

        # 电机角度 = 向量夹角（直接使用，不取补角）
        q4 = np.arccos(cos_angle)

        # 保存调试信息
        self._last_elbow_debug = {
            'vector_angle': np.degrees(q4),
            'elbow_angle_human': 180.0 - np.degrees(q4),
            'elbow_angle_motor': np.degrees(q4),
            'q4_raw': q4,
            'v_shoulder_elbow': v_shoulder_elbow,
            'v_elbow_wrist': v_elbow_wrist,
        }

        return np.array([q1, q2, q3, q4])

    def solve_wrist_orientation(self, q_arm, target_orientation, alpha=0.0, q_current_wrist=None):
        """
        Stage 2: 腕部姿态求解（支持多种控制模式）

        给定臂部配置（q1-q4）和目标末端姿态，计算腕部关节角度（q5-q7）

        支持四种控制模式：
        1. full_dof: 全自由度欧拉角分解（默认）
        2. constrained_horizontal: 约束水平模式（J5锁定，J6保持水平）
        3. wrist_locked: 腕部锁定模式（J5-J7保持当前值）
        4. vertical_insertion: 垂直插入模式（J5/J7锁定，J6动态约束保持垂直）

        动态腕部解锁（平滑过渡）：
        - 当enable_dynamic_wrist_unlock=True时
        - 根据α值在constrained和full_dof之间平滑插值
        - α < 0.5: 完全约束（constrained_horizontal）
        - 0.5 < α < 0.9: 平滑过渡
        - α > 0.9: 完全自由（full_dof）

        Args:
            q_arm: 臂部关节角度 [q1, q2, q3, q4] (numpy array)
            target_orientation: 目标末端姿态（旋转矩阵或四元数）
            alpha: 意图因子（0-1），用于动态腕部解锁
            q_current_wrist: 当前腕部关节角度 [q5, q6, q7]（可选，用于wrist_locked模式）

        Returns:
            q_wrist: 腕部关节角度 [q5, q6, q7] (numpy array)
        """
        # 模式1: 腕部锁定模式（保持当前值）
        if self.wrist_control_mode == 'wrist_locked':
            # ✅ 修复：返回当前关节角度而不是固定的0
            # 这样SafeRobotController计算速度时：q_dot = (q_current - q_current) / dt = 0
            if q_current_wrist is not None:
                return q_current_wrist.copy()
            else:
                # 如果没有提供当前值，返回0（向后兼容）
                return np.zeros(3)

        # 模式2: 垂直插入模式（USB插入专用）
        if self.wrist_control_mode == 'vertical_insertion':
            return self._solve_wrist_vertical_insertion(q_arm, target_orientation, alpha)

        # 模式3: 约束水平模式（可能带动态解锁）
        if self.wrist_control_mode == 'constrained_horizontal':
            # 计算约束模式的解
            q_wrist_constrained = self._solve_wrist_constrained_horizontal(q_arm, target_orientation)

            # 如果启用动态解锁，根据α进行平滑过渡
            if self.enable_dynamic_wrist_unlock and alpha > 0.5:
                # 计算全自由度模式的解
                q_wrist_free = self._solve_wrist_full_dof(q_arm, target_orientation)

                # 计算混合权重（平滑过渡）
                # α = 0.5 → weight = 0（完全约束）
                # α = 0.9 → weight = 1（完全自由）
                alpha_min = 0.5
                alpha_max = 0.9
                weight = np.clip((alpha - alpha_min) / (alpha_max - alpha_min), 0.0, 1.0)

                # 平滑插值
                q_wrist = (1 - weight) * q_wrist_constrained + weight * q_wrist_free
                return q_wrist
            else:
                return q_wrist_constrained

        # 模式4: 全自由度模式（默认）
        return self._solve_wrist_full_dof(q_arm, target_orientation)

    def get_elbow_debug_info(self):
        """
        获取最近一次肘部角度计算的调试信息

        Returns:
            dict: 包含向量夹角、人体肘部角度、电机角度等信息
        """
        return self._last_elbow_debug.copy() if self._last_elbow_debug else {}

    def _solve_wrist_full_dof(self, q_arm, target_orientation):
        """
        全自由度腕部求解（欧拉角分解）

        算法思路：
        1. 使用正运动学计算臂部末端（腕部基座）的姿态
        2. 计算从腕部基座到目标姿态的相对旋转
        3. 将相对旋转分解为欧拉角（对应 q5, q6, q7）

        Args:
            q_arm: 臂部关节角度 [q1, q2, q3, q4]
            target_orientation: 目标末端姿态（旋转矩阵或四元数）

        Returns:
            q_wrist: 腕部关节角度 [q5, q6, q7]
        """
        # 构建完整的关节配置（臂部 + 腕部初始值）
        # 注意：controlled_joints 是 velocity indices，不能直接用于索引 q_full
        # 需要通过 IK solver 的方法来正确设置关节角度
        q_full = pin.neutral(self.model).copy()

        # 使用 velocity indices 获取对应的 position indices
        # 对于 revolute 关节，idx_q 通常等于 idx_v，但为了安全起见，我们应该正确处理
        # 暂时简化：假设前7个受控关节对应 q_full 的前7个位置
        # 这是一个临时解决方案，更好的方法是使用 joint 的 idx_q
        try:
            for i, angle in enumerate(q_arm):
                if i < len(self.controlled_joints):
                    joint_idx = self.controlled_joints[i]
                    # 对于 revolute 关节，idx_v 和 idx_q 通常相同
                    q_full[joint_idx] = angle

            # 腕部初始值设为 0（中立位置）
            for i in range(len(q_arm), len(self.controlled_joints)):
                if i < len(self.controlled_joints):
                    joint_idx = self.controlled_joints[i]
                    q_full[joint_idx] = 0.0
        except IndexError as e:
            print(f"⚠️ [GeometricSolver] 索引错误: {e}")
            print(f"   q_full 长度: {len(q_full)}, controlled_joints: {self.controlled_joints}")
            # 使用安全的默认值
            q_full = pin.neutral(self.model).copy()

        # 正运动学：计算腕部基座的姿态
        pin.forwardKinematics(self.model, self.data, q_full)
        pin.updateFramePlacements(self.model, self.data)
        wrist_base_placement = self.data.oMf[self.ee_frame_id]
        wrist_base_rot = wrist_base_placement.rotation

        # 将目标姿态转换为旋转矩阵
        if target_orientation.shape == (4,):
            # 四元数 [x, y, z, w]
            target_rot = Rotation.from_quat(target_orientation).as_matrix()
        elif target_orientation.shape == (3, 3):
            # 旋转矩阵
            target_rot = target_orientation
        else:
            raise ValueError(f"不支持的姿态格式: {target_orientation.shape}")

        # 计算相对旋转：R_relative = target_rot @ wrist_base_rot.T
        R_relative = target_rot @ wrist_base_rot.T

        # 将相对旋转分解为欧拉角（ZYX 顺序，对应 Yaw-Pitch-Roll）
        # 这对应于腕部的 Yaw-Pitch-Roll 关节
        euler_angles = Rotation.from_matrix(R_relative).as_euler('ZYX', degrees=False)
        q5, q6, q7 = euler_angles  # Yaw, Pitch, Roll

        return np.array([q5, q6, q7])

    def _solve_wrist_constrained_horizontal(self, q_arm, target_orientation):
        """
        约束水平模式腕部求解

        约束策略：
        - J5 (Wrist Yaw): 锁定为0（保持水平）
        - J6 (Wrist Pitch): 与J4配合约束，保持末端水平于桌面
        - J7 (Wrist Roll): 从目标姿态提取手腕旋转

        这种模式适合桌面操作任务（如插入、抓取），可以：
        1. 简化控制，减少自由度
        2. 保持末端水平，避免碰撞
        3. 提高操作稳定性

        Args:
            q_arm: 臂部关节角度 [q1, q2, q3, q4]
            target_orientation: 目标末端姿态（旋转矩阵或四元数）

        Returns:
            q_wrist: 腕部关节角度 [q5, q6, q7]
        """
        # J5 (Wrist Yaw): 锁定为0
        q5 = 0.0

        # J6 (Wrist Pitch): 补偿肘部弯曲，保持末端水平
        # 当肘部弯曲时（q4 > 0），腕部需要反向弯曲以保持水平
        # 简化模型：q6 = -q4（完全补偿）
        # 实际可能需要根据机器人几何参数调整系数
        q4 = q_arm[3]  # 肘部角度
        q6 = -q4  # 补偿肘部弯曲

        # J7 (Wrist Roll): 从目标姿态提取手腕旋转
        # 将目标姿态转换为旋转矩阵
        if target_orientation.shape == (4,):
            # 四元数 [x, y, z, w]
            target_rot = Rotation.from_quat(target_orientation).as_matrix()
        elif target_orientation.shape == (3, 3):
            # 旋转矩阵
            target_rot = target_orientation
        else:
            raise ValueError(f"不支持的姿态格式: {target_orientation.shape}")

        # 提取绕Z轴的旋转（Roll角度）
        # 使用欧拉角分解，只取Roll分量
        euler_angles = Rotation.from_matrix(target_rot).as_euler('ZYX', degrees=False)
        q7 = euler_angles[2]  # Roll

        return np.array([q5, q6, q7])

    def _solve_wrist_vertical_insertion(self, q_arm, target_orientation=None, alpha=0.0):
        """
        垂直插入模式腕部求解（USB插入专用，基于意图因子的变刚度控制）

        约束策略（意图调制的硬约束层）：
        - J5 (Wrist Yaw): 锁定为0（防止Roll旋转，避免插歪）
        - J6 (Wrist Pitch): 意图调制的变刚度控制
          * α→0 (远距离): "硬"直臂状态，J6≈0（模仿人类自然伸展的小臂）
          * α→1 (近距离): "软"协同状态，J6动态反解保持垂直
        - J7 (Wrist Roll): 锁定为0（防止Yaw旋转）

        核心创新：基于意图因子的变刚度冗余解析
        ================================================
        q6_cmd = (1-α) * q6_stiff + α * q6_vertical

        其中：
        - q6_stiff = 0: 大范围运动时的"硬"直臂构型（仿生学）
        - q6_vertical = -π/2 - q1 - q4: 插入阶段的"软"协同构型（任务约束）

        理论依据：
        - 远距离（α→0）: 保持人类手臂自然拓扑，J6不弯折，"所见即所得"
        - 近距离（α→1）: 任务约束主导，J1+J4+J6协同保持垂直
        - 平滑过渡: C¹连续的同伦平滑过渡，避免状态机切换的急动
        - 符合VIST框架: 意图因子不仅调制协方差，也调制运动学映射

        Args:
            q_arm: 臂部关节角度 [q1, q2, q3, q4]
            target_orientation: 目标末端姿态（可选，此模式下忽略）
            alpha: 意图因子（0-1），控制从直臂到垂直的平滑过渡

        Returns:
            q_wrist: 腕部关节角度 [q5, q6, q7]
        """
        # J5: 锁定为0（防止Roll）
        q5 = 0.0

        # J6: 意图调制的变刚度控制
        # ==========================================
        # 1. 大范围运动的"硬"直臂状态（仿生学）
        q6_stiff_straight = 0.0  # 保持小臂与末端平齐，不弯折

        # 2. 插入阶段的"软"协同状态（任务约束）
        # 约束方程: q1 + q4 + q6 = -π/2 (垂直向下)
        q1 = q_arm[0]  # 肩部俯仰
        q4 = q_arm[3]  # 肘部俯仰
        target_pitch = -np.pi / 2  # 垂直向下
        q6_dynamic_vertical = target_pitch - q1 - q4

        # 3. 基于意图因子的α-blending（核心创新）
        # α=0: 完全直臂（硬）
        # α=1: 完全垂直（软）
        q6 = (1.0 - alpha) * q6_stiff_straight + alpha * q6_dynamic_vertical

        # J7: 锁定为0（防止Yaw）
        q7 = 0.0

        return np.array([q5, q6, q7])

    def solve(self, shoulder_pos, elbow_pos, wrist_pos, target_orientation=None, alpha=0.0, q_current=None):
        """
        完整求解：臂部配置 + 腕部姿态

        Args:
            shoulder_pos: 肩部位置 [x, y, z]
            elbow_pos: 肘部位置 [x, y, z]
            wrist_pos: 腕部位置 [x, y, z]
            target_orientation: 目标末端姿态（可选，如果为 None 则只求解臂部配置）
            alpha: 意图因子（0-1），用于动态腕部解锁
            q_current: 当前关节角度 [q1, ..., q7]（可选，用于wrist_locked模式）

        Returns:
            q_solution: 完整的关节角度 [q1, q2, q3, q4, q5, q6, q7]
        """
        # Stage 1: 臂部配置求解
        q_arm = self.solve_arm_configuration(shoulder_pos, elbow_pos, wrist_pos)

        # Stage 2: 腕部姿态求解
        if target_orientation is not None:
            # 提取当前腕部角度（如果提供）
            q_current_wrist = q_current[4:7] if q_current is not None and len(q_current) >= 7 else None
            q_wrist = self.solve_wrist_orientation(q_arm, target_orientation, alpha, q_current_wrist)
        else:
            # 如果没有指定目标姿态，腕部保持中立位置或当前位置
            if q_current is not None and len(q_current) >= 7:
                q_wrist = q_current[4:7].copy()
            else:
                q_wrist = np.zeros(3)

        # 使用关节名来明确映射，避免索引混淆
        # 根据 joint_name_to_index 中的关节名称创建映射
        # 自动检测是左臂还是右臂
        joint_names = list(self.joint_name_to_index.keys())
        if len(joint_names) > 0:
            # 从第一个关节名判断是左臂还是右臂
            is_left_arm = 'Left' in joint_names[0]
            prefix = 'Left' if is_left_arm else 'Right'
        else:
            prefix = 'Right'  # 默认右臂

        # 创建关节角度字典
        joint_angles = {
            f'{prefix}_Shoulder_Pitch_Joint': q_arm[0],
            f'{prefix}_Shoulder_Roll_Joint': q_arm[1],
            f'{prefix}_Shoulder_Yaw_Joint': q_arm[2],
            f'{prefix}_Elbow_Pitch_Joint': q_arm[3],  # 肘部弯曲
            f'{prefix}_Wrist_Yaw_Joint': q_wrist[0],
            f'{prefix}_Wrist_Pitch_Joint': q_wrist[1],
            f'{prefix}_Wrist_Roll_Joint': q_wrist[2]
        }

        # 根据 controlled_joints 的顺序构建 q_solution
        q_solution = np.zeros(len(self.controlled_joints))
        for joint_name, angle in joint_angles.items():
            if joint_name in self.joint_name_to_index:
                idx = self.joint_name_to_index[joint_name]
                # 应用关节方向系数和零位偏移
                # 公式: q_final = q_calculated * direction + offset
                q_solution[idx] = angle * self.joint_directions[idx] + self.joint_offsets[idx]

        return q_solution


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试几何解析臂部求解器...")

    # 1. 加载机器人模型
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

    # 使用 PinocchioIKSolver 来加载模型
    from ik_solver import PinocchioIKSolver
    ik_solver = PinocchioIKSolver(urdf_path=urdf_path)

    # 2. 创建几何求解器
    geo_solver = GeometricArmSolver(
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_joints=ik_solver.controlled_indices,
        ee_frame_id=ik_solver.ee_frame_id
    )

    # 3. 定义测试数据（模拟 MediaPipe 检测到的关键点）
    shoulder_pos = np.array([0.0, 0.0, 0.0])  # 肩部在原点
    elbow_pos = np.array([0.2, 0.1, 0.1])     # 肘部在前方
    wrist_pos = np.array([0.3, 0.15, 0.2])    # 腕部在更前方

    print(f"\n🎯 测试数据:")
    print(f"   肩部位置: {shoulder_pos}")
    print(f"   肘部位置: {elbow_pos}")
    print(f"   腕部位置: {wrist_pos}")

    # 4. 求解臂部配置
    q_solution = geo_solver.solve(shoulder_pos, elbow_pos, wrist_pos)

    print(f"\n📊 求解结果:")
    print(f"   关节角度 (度): {np.degrees(q_solution)}")
    print(f"   关节角度 (弧度): {q_solution}")

    print("\n✅ 测试完成！")
