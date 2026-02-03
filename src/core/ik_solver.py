"""
Pinocchio-based Inverse Kinematics Solver for VIST Project

This module implements a CLIK (Closed-Loop Inverse Kinematics) solver
that converts target end-effector poses (position + orientation) into
joint angles for the robot arm.

Algorithm: Damped Least Squares (DLS) method with iterative refinement
- Computes Jacobian matrix at each iteration
- Uses damped pseudo-inverse to avoid singularities
- Supports joint limits and convergence criteria

Version 1.0: Position-only tracking (3-DoF)
- Orientation error is computed but set to zero
- Future versions will add full 6-DoF tracking
"""

import numpy as np
import pinocchio as pin
from scipy.spatial.transform import Rotation
import os
import tempfile


class PinocchioIKSolver:
    """
    基于 Pinocchio 的逆运动学求解器

    使用 CLIK (Closed-Loop Inverse Kinematics) 算法，
    通过迭代优化将目标位姿转换为关节角度。

    支持特定运动链优化：只优化指定的关节，提高收敛速度和精度。
    """

    # 默认的右臂 7-DoF 关节名称列表
    DEFAULT_RIGHT_ARM_JOINTS = [
        "Right_Shoulder_Pitch_Joint",
        "Right_Shoulder_Roll_Joint",
        "Right_Shoulder_Yaw_Joint",
        "Right_Elbow_Pitch_Joint",
        "Right_Wrist_Yaw_Joint",
        "Right_Wrist_Pitch_Joint",
        "Right_Wrist_Roll_Joint"
    ]

    def __init__(self, urdf_path=None, end_effector_frame="hand_base_link",
                 controlled_joints=None):
        """
        初始化 IK 求解器

        Args:
            urdf_path: URDF 文件路径（默认使用项目配置）
            end_effector_frame: 末端执行器 frame 名称（默认 hand_base_link）
            controlled_joints: 需要控制的关节名称列表（默认使用右臂 7-DoF）
                             如果为 None，使用 DEFAULT_RIGHT_ARM_JOINTS
                             如果为空列表 []，则控制所有关节
        """
        print(f"🧠 [IKSolver] 初始化逆运动学求解器...")

        # 1. 获取项目根目录和 URDF 路径
        if urdf_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            urdf_path = os.path.join(project_root, "config", "robot.urdf")

        print(f"📁 [IKSolver] 加载 URDF: {urdf_path}")

        # 2. 动态路径替换策略（复用 viz_server 的逻辑）
        # 读取原始 URDF 内容
        with open(urdf_path, 'r', encoding='utf-8') as f:
            urdf_content = f.read()

        # 替换 package://my_robot/ 为 config 目录的绝对路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_dir = os.path.join(project_root, "config")
        config_dir_uri = f"file://{config_dir}/"
        urdf_content_fixed = urdf_content.replace("package://my_robot/", config_dir_uri)

        print(f"🔧 [IKSolver] 路径替换: package://my_robot/ -> {config_dir_uri}")

        # 3. 创建临时 URDF 文件
        self.temp_urdf = tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.urdf',
            delete=False,  # 不自动删除
            encoding='utf-8'
        )
        self.temp_urdf.write(urdf_content_fixed)
        self.temp_urdf.close()

        print(f"📝 [IKSolver] 临时 URDF: {self.temp_urdf.name}")

        # 4. 加载 Pinocchio 模型
        self.robot = pin.RobotWrapper.BuildFromURDF(self.temp_urdf.name)
        self.model = self.robot.model
        self.data = self.robot.data

        # 5. 查找末端执行器 frame ID
        self.ee_frame_name = end_effector_frame
        if self.model.existFrame(self.ee_frame_name):
            self.ee_frame_id = self.model.getFrameId(self.ee_frame_name)
            print(f"✅ [IKSolver] 找到末端执行器 frame: {self.ee_frame_name} (ID={self.ee_frame_id})")
        else:
            raise ValueError(f"❌ [IKSolver] 未找到 frame: {self.ee_frame_name}")

        # 6. 初始化关节配置（中立位置）
        self.q = pin.neutral(self.model).copy()

        # 7. 获取关节限位
        self.q_min = self.model.lowerPositionLimit
        self.q_max = self.model.upperPositionLimit

        # 8. 设置受控关节（Chain-specific Optimization）
        if controlled_joints is None:
            # 默认使用右臂 7-DoF
            controlled_joints = self.DEFAULT_RIGHT_ARM_JOINTS

        self.controlled_joints = controlled_joints

        if len(controlled_joints) == 0:
            # 空列表表示控制所有关节
            print(f"⚙️ [IKSolver] 控制模式: 全关节优化 ({self.model.nv} 个自由度)")
            self.controlled_indices = list(range(self.model.nv))
        else:
            # 查找指定关节的 velocity indices
            self.controlled_indices = []
            print(f"⚙️ [IKSolver] 控制模式: 特定运动链优化")
            for joint_name in controlled_joints:
                try:
                    # 获取关节 ID
                    joint_id = self.model.getJointId(joint_name)
                    # 获取该关节在速度空间的索引
                    idx_v = self.model.joints[joint_id].idx_v
                    # 获取该关节的自由度数量
                    nv = self.model.joints[joint_id].nv

                    # 对于 revolute 关节，nv=1；对于其他类型可能 >1
                    for offset in range(nv):
                        self.controlled_indices.append(idx_v + offset)

                    print(f"   ✓ {joint_name}: velocity_index={idx_v}, nv={nv}")
                except Exception as e:
                    print(f"   ✗ {joint_name}: 未找到 ({e})")

            if len(self.controlled_indices) == 0:
                raise ValueError("❌ [IKSolver] 没有找到任何有效的受控关节！")

            print(f"   总共控制 {len(self.controlled_indices)} 个自由度")

        print(f"✅ [IKSolver] 初始化完成")
        print(f"   关节数量: {self.model.nq}")
        print(f"   速度维度: {self.model.nv}")
        print(f"   受控自由度: {len(self.controlled_indices)}")


    def solve(self, target_pos, target_quat=None, q_init=None,
              max_iter=50, tol=1e-3, damping=1e-3, dt=1.0,
              pos_weight=1.0, rot_weight=0.5):
        """
        求解逆运动学：将目标位姿转换为关节角度

        算法：CLIK (Closed-Loop Inverse Kinematics)
        - 迭代优化，每次计算雅可比矩阵
        - 使用阻尼最小二乘法（Damped Least Squares）避免奇异点
        - 支持关节限位截断
        - 特定运动链优化：只优化指定的关节
        - 支持 6-DoF 姿态追踪（位置 + 旋转）

        Args:
            target_pos: 目标位置 [x, y, z] (numpy array, 米)
            target_quat: 目标姿态四元数 [x, y, z, w] (numpy array)
                        如果为 None，则只追踪位置（3-DoF）
            q_init: 初始关节角度猜测 (numpy array, 默认使用上次结果)
            max_iter: 最大迭代次数（默认 50）
            tol: 收敛阈值（默认 1mm）
            damping: 阻尼系数（默认 1e-3，用于避免奇异点）
            dt: 时间步长（默认 1.0，控制收敛速度）
            pos_weight: 位置误差权重（默认 1.0）
            rot_weight: 旋转误差权重（默认 0.5，姿态次于位置）

        Returns:
            q_solution: 求解的关节角度 (numpy array)
            success: 是否成功收敛 (bool)
            error: 最终误差 (float, 米)
        """
        # ==========================================
        # Step 1: 初始化
        # ==========================================
        # 如果提供了初始猜测，使用它；否则使用上次的结果
        if q_init is not None:
            q = q_init.copy()
        else:
            q = self.q.copy()

        target_pos = np.array(target_pos, dtype=np.float64)

        # 判断是否追踪姿态
        track_orientation = (target_quat is not None)
        if track_orientation:
            target_quat = np.array(target_quat, dtype=np.float64)
            # 将四元数转换为旋转矩阵（Pinocchio 使用 [x,y,z,w] 格式）
            target_rot = Rotation.from_quat(target_quat).as_matrix()

        # ==========================================
        # Step 2: 迭代优化
        # ==========================================
        for i in range(max_iter):
            # 2.1 正运动学：计算当前末端位置
            pin.forwardKinematics(self.model, self.data, q)
            pin.updateFramePlacements(self.model, self.data)

            # 获取当前末端执行器的位姿
            ee_placement = self.data.oMf[self.ee_frame_id]
            curr_pos = ee_placement.translation  # 当前位置
            curr_rot = ee_placement.rotation     # 当前旋转矩阵

            # 2.2 计算位置误差（3-DoF）
            pos_error = target_pos - curr_pos

            # 2.3 计算姿态误差（3-DoF，使用 SO3 对数映射）
            if track_orientation:
                # ==========================================
                # 【6-DoF 姿态追踪】计算旋转误差
                # ==========================================
                # 计算旋转误差矩阵：R_error = target_rot @ curr_rot.T
                # 这表示从当前姿态到目标姿态的旋转
                R_error = target_rot @ curr_rot.T

                # 使用 Pinocchio 的 log3 函数将旋转矩阵转换为轴角表示
                # 这给出了 SO(3) Lie 代数中的误差向量
                rot_error = pin.log3(R_error)
            else:
                # 只追踪位置，姿态误差置零
                rot_error = np.zeros(3)

            # 2.4 合并误差向量（应用权重）
            if track_orientation:
                # 6-DoF: [位置误差 * pos_weight, 姿态误差 * rot_weight]
                error_vector = np.concatenate([
                    pos_error * pos_weight,
                    rot_error * rot_weight
                ])
                error_dim = 6
            else:
                # 3-DoF: 只有位置误差
                error_vector = pos_error * pos_weight
                error_dim = 3

            # 2.5 检查收敛条件
            # 对于 6-DoF，同时检查位置和姿态误差
            pos_error_norm = np.linalg.norm(pos_error)

            if track_orientation:
                rot_error_norm = np.linalg.norm(rot_error)
                # 6-DoF: 位置和姿态都要满足阈值
                # 位置阈值：tol (默认 1mm)
                # 姿态阈值：tol * 10 (默认 10mm，对应约 0.01 弧度)
                pos_converged = pos_error_norm < tol
                rot_converged = rot_error_norm < (tol * 10)
                converged = pos_converged and rot_converged

                if converged:
                    print(f"✅ [IKSolver] 6-DoF 收敛成功！迭代次数: {i+1}")
                    print(f"   位置误差: {pos_error_norm*1000:.2f}mm")
                    print(f"   姿态误差: {rot_error_norm:.4f} rad ({np.degrees(rot_error_norm):.2f}°)")
                    self.q = q.copy()
                    return q, True, pos_error_norm
            else:
                # 3-DoF: 只检查位置误差
                if pos_error_norm < tol:
                    print(f"✅ [IKSolver] 收敛成功！迭代次数: {i+1}, 误差: {pos_error_norm*1000:.2f}mm")
                    self.q = q.copy()
                    return q, True, pos_error_norm

            # 2.6 计算雅可比矩阵
            # Pinocchio 的雅可比矩阵是 6xN 的（前3行是线速度，后3行是角速度）
            J_full = pin.computeFrameJacobian(
                self.model, self.data, q, self.ee_frame_id,
                pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
            )

            # 根据追踪模式选择雅可比矩阵
            if track_orientation:
                # 6-DoF: 使用完整的雅可比矩阵（位置 + 旋转）
                J_full_6d = J_full  # 6 x nv 矩阵
            else:
                # 3-DoF: 只使用位置部分的雅可比矩阵
                J_full_6d = J_full[:3, :]  # 3 x nv 矩阵

            # ==========================================
            # 【关键优化】只提取受控关节对应的列
            # ==========================================
            J = J_full_6d[:, self.controlled_indices]  # error_dim x n_controlled 矩阵

            # 2.7 计算阻尼最小二乘伪逆（Damped Least Squares）
            # 公式: J_pinv = J^T @ (J @ J^T + λ^2 * I)^(-1)
            # 这种方法在接近奇异点时更稳定
            JJT = J @ J.T  # error_dim x error_dim 矩阵
            damping_matrix = damping**2 * np.eye(error_dim)
            J_pinv = J.T @ np.linalg.inv(JJT + damping_matrix)

            # 2.8 计算关节速度（只针对受控关节）
            # dq_controlled = J_pinv @ error_vector
            dq_controlled = J_pinv @ error_vector

            # 2.9 更新关节角度（只更新受控关节）
            # 创建完整的速度向量（其他关节速度为 0）
            dq_full = np.zeros(self.model.nv)
            dq_full[self.controlled_indices] = dq_controlled

            # 使用 Pinocchio 的积分函数更新关节角度
            # q_new = pin.integrate(model, q, dq * dt)
            q = pin.integrate(self.model, q, dq_full * dt)

            # 2.10 关节限位截断（Clip to Joint Limits）
            # 确保关节角度在允许范围内
            q = np.clip(q, self.q_min, self.q_max)

            # 2.11 调试输出（每10次迭代打印一次）
            if (i + 1) % 10 == 0:
                if track_orientation:
                    print(f"   迭代 {i+1}/{max_iter}: 位置误差={pos_error_norm*1000:.2f}mm, 姿态误差={rot_error_norm:.4f}rad")
                else:
                    print(f"   迭代 {i+1}/{max_iter}: 误差 = {pos_error_norm*1000:.2f}mm")

        # ==========================================
        # Step 3: 未收敛
        # ==========================================
        print(f"⚠️ [IKSolver] 未收敛！达到最大迭代次数 {max_iter}, 最终误差: {pos_error_norm*1000:.2f}mm")
        self.q = q.copy()  # 仍然保存结果（可能是局部最优）
        return q, False, pos_error_norm

    def cleanup(self):
        """清理临时文件"""
        if hasattr(self, 'temp_urdf') and os.path.exists(self.temp_urdf.name):
            try:
                os.unlink(self.temp_urdf.name)
                print(f"🗑️ [IKSolver] 已清理临时文件: {self.temp_urdf.name}")
            except Exception as e:
                print(f"⚠️ [IKSolver] 清理临时文件失败: {e}")

    def __del__(self):
        """析构函数：自动清理临时文件"""
        self.cleanup()


# ==========================================
# 测试代码
# ==========================================
if __name__ == "__main__":
    print("🧪 测试 IK 求解器...")

    # 1. 创建求解器（使用默认的右臂 7-DoF）
    print("\n" + "="*60)
    print("测试 1: 3-DoF 位置追踪")
    print("="*60)
    solver = PinocchioIKSolver()

    # 2. 定义目标位置（在机器人前方 30cm）
    target_pos = np.array([0.3, 0.0, 0.3])
    print(f"\n🎯 目标位置: {target_pos}")

    # 3. 求解 IK（只追踪位置）
    q_solution, success, error = solver.solve(target_pos, max_iter=100)

    # 4. 输出结果
    print(f"\n📊 求解结果:")
    print(f"   成功: {success}")
    print(f"   最终误差: {error*1000:.2f}mm")

    # 5. 验证：正运动学检查
    pin.forwardKinematics(solver.model, solver.data, q_solution)
    pin.updateFramePlacements(solver.model, solver.data)
    ee_placement = solver.data.oMf[solver.ee_frame_id]
    actual_pos = ee_placement.translation
    print(f"\n✅ 验证（正运动学）:")
    print(f"   目标位置: {target_pos}")
    print(f"   实际位置: {actual_pos}")
    print(f"   误差: {np.linalg.norm(target_pos - actual_pos)*1000:.2f}mm")

    # ==========================================
    # 测试 6-DoF 姿态追踪
    # ==========================================
    print("\n" + "="*60)
    print("测试 2: 6-DoF 姿态追踪（位置 + 旋转）")
    print("="*60)

    # 定义目标位置和姿态
    target_pos_6d = np.array([0.3, 0.1, 0.3])
    # 定义一个旋转：绕 Z 轴旋转 45 度
    target_rot = Rotation.from_euler('z', 45, degrees=True)
    target_quat = target_rot.as_quat()  # [x, y, z, w]

    print(f"\n🎯 目标位置: {target_pos_6d}")
    print(f"   目标四元数: {target_quat}")

    # 求解 6-DoF IK
    q_solution_6d, success_6d, error_6d = solver.solve(
        target_pos_6d,
        target_quat=target_quat,
        q_init=q_solution,  # 使用上一次的结果作为初始猜测
        max_iter=100
    )

    print(f"\n📊 求解结果:")
    print(f"   成功: {success_6d}")
    print(f"   最终误差: {error_6d*1000:.2f}mm")

    # 验证
    pin.forwardKinematics(solver.model, solver.data, q_solution_6d)
    pin.updateFramePlacements(solver.model, solver.data)
    ee_placement_6d = solver.data.oMf[solver.ee_frame_id]
    actual_pos_6d = ee_placement_6d.translation
    actual_rot_6d = ee_placement_6d.rotation
    actual_quat_6d = Rotation.from_matrix(actual_rot_6d).as_quat()

    print(f"\n✅ 验证（正运动学）:")
    print(f"   位置误差: {np.linalg.norm(target_pos_6d - actual_pos_6d)*1000:.2f}mm")
    print(f"   目标四元数: {target_quat}")
    print(f"   实际四元数: {actual_quat_6d}")
    print(f"   四元数差异: {np.linalg.norm(target_quat - actual_quat_6d):.4f}")



