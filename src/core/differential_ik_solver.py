#!/usr/bin/env python3
"""
Differential IK Solver - VIST Framework Implementation
基于微分运动学的IK求解器，实现VIST框架的核心思想

核心优势：
1. 不求解全局IK，只计算增量 Δq
2. 计算速度快（无需迭代优化）
3. 天然保证连续性
4. 不会陷入局部最小值
"""

import numpy as np
import pinocchio as pin
import os
import tempfile


class DifferentialIKSolver:
    """基于微分运动学的IK求解器"""

    def __init__(self, urdf_path=None, end_effector_frame="Right_Wrist_Roll_Link", elbow_frame="Right_Elbow_Pitch_Link"):
        """
        初始化微分IK求解器

        Args:
            urdf_path: URDF文件路径，如果为None则使用默认路径
            end_effector_frame: 末端执行器frame名称
            elbow_frame: 肘部frame名称（用于双目标优化）
        """
        print("🧠 [DifferentialIK] 初始化微分IK求解器...")

        # 1. 加载URDF
        if urdf_path is None:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
            urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")

        # 2. 创建临时URDF（移除固定关节）
        self.temp_urdf = self._create_temp_urdf(urdf_path)

        # 3. 加载模型
        self.model = pin.buildModelFromUrdf(self.temp_urdf.name)
        self.data = self.model.createData()

        # 4. 获取末端执行器frame ID
        self.ee_frame_name = end_effector_frame
        if not self.model.existFrame(self.ee_frame_name):
            raise ValueError(f"末端执行器frame '{self.ee_frame_name}' 不存在")

        self.ee_frame_id = self.model.getFrameId(self.ee_frame_name)

        # 5. 获取肘部frame ID（用于双目标优化）
        self.elbow_frame_name = elbow_frame
        if not self.model.existFrame(self.elbow_frame_name):
            raise ValueError(f"肘部frame '{self.elbow_frame_name}' 不存在")

        self.elbow_frame_id = self.model.getFrameId(self.elbow_frame_name)

        # 6. 初始化关节配置
        self.q = pin.neutral(self.model)

        # 7. 控制参数
        self.damping = 1e-2  # 阻尼系数（用于伪逆计算）

        print(f"✅ [DifferentialIK] 初始化完成")
        print(f"   关节数量: {self.model.nq}")
        print(f"   末端执行器: {self.ee_frame_name}")
        print(f"   肘部frame: {self.elbow_frame_name}")

    def _create_temp_urdf(self, urdf_path):
        """创建临时URDF文件"""
        with open(urdf_path, 'r') as f:
            urdf_content = f.read()

        # 不修改 joint 类型，保持 fixed
        # （如果改为 floating 会增加 7 个自由度，导致 nq=14）

        temp_urdf = tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False)
        temp_urdf.write(urdf_content)
        temp_urdf.flush()

        return temp_urdf

    def compute_jacobian(self, q, frame_id=None):
        """
        计算指定frame的雅可比矩阵

        Args:
            q: 当前关节角度 (14,) 或 (7,)
            frame_id: frame ID，如果为None则使用末端执行器

        Returns:
            J: 雅可比矩阵 (6, nq) - 前3行是位置，后3行是姿态
        """
        if frame_id is None:
            frame_id = self.ee_frame_id

        # 更新运动学
        pin.forwardKinematics(self.model, self.data, q)
        pin.updateFramePlacements(self.model, self.data)

        # 计算雅可比矩阵（世界坐标系）
        J = pin.computeFrameJacobian(
            self.model, self.data, q, frame_id,
            pin.ReferenceFrame.LOCAL_WORLD_ALIGNED
        )

        return J

    def damped_pseudoinverse(self, J, damping=None):
        """
        计算阻尼伪逆（Damped Pseudo-inverse）

        使用阻尼最小二乘法避免奇异性：
        J† = J^T (JJ^T + λ²I)^(-1)

        Args:
            J: 雅可比矩阵 (m, n)
            damping: 阻尼系数，如果为None则使用self.damping

        Returns:
            J_pinv: 阻尼伪逆 (n, m)
        """
        if damping is None:
            damping = self.damping

        m, n = J.shape

        # 阻尼最小二乘法
        J_pinv = J.T @ np.linalg.inv(J @ J.T + (damping ** 2) * np.eye(m))

        return J_pinv

    def solve_dual_target(self, target_wrist_pos, target_elbow_pos, q_init=None,
                          wrist_weight=1.0, elbow_weight=0.5, gain=1.0):
        """
        双目标微分IK求解：同时优化肘部和手腕位置

        核心思想：
        J_combined = [w_wrist * J_wrist; w_elbow * J_elbow]
        error_combined = [w_wrist * error_wrist; w_elbow * error_elbow]
        Δq = J_combined† @ error_combined

        Args:
            target_wrist_pos: 手腕目标位置 (3,)
            target_elbow_pos: 肘部目标位置 (3,)
            q_init: 初始关节角度 (7,) 右臂关节
            wrist_weight: 手腕权重（默认1.0）
            elbow_weight: 肘部权重（默认0.5）
            gain: 增益系数（0-1）

        Returns:
            q_solution: 求解的关节角度 (7,) 右臂关节
            success: 是否成功
            wrist_error: 手腕位置误差（米）
            elbow_error: 肘部位置误差（米）
        """
        # 1. 初始化
        if q_init is not None:
            if len(q_init) == 7:
                self.q = np.concatenate([np.zeros(7), q_init])
            else:
                self.q = q_init.copy()

        # 2. 计算当前肘部和手腕位置
        pin.forwardKinematics(self.model, self.data, self.q)
        pin.updateFramePlacements(self.model, self.data)

        elbow_placement = self.data.oMf[self.elbow_frame_id]
        wrist_placement = self.data.oMf[self.ee_frame_id]

        current_elbow_pos = elbow_placement.translation
        current_wrist_pos = wrist_placement.translation

        # 3. 计算误差
        error_elbow = target_elbow_pos - current_elbow_pos
        error_wrist = target_wrist_pos - current_wrist_pos

        # 4. 计算雅可比矩阵
        J_elbow_full = self.compute_jacobian(self.q, self.elbow_frame_id)
        J_wrist_full = self.compute_jacobian(self.q, self.ee_frame_id)

        # 只使用位置部分（前3行）
        J_elbow = J_elbow_full[:3, :]
        J_wrist = J_wrist_full[:3, :]

        # 5. 构建组合雅可比和误差（加权堆叠）
        J_combined = np.vstack([
            wrist_weight * J_wrist,
            elbow_weight * J_elbow
        ])  # (6, 14)

        error_combined = np.concatenate([
            wrist_weight * error_wrist,
            elbow_weight * error_elbow
        ])  # (6,)

        # 6. 计算关节增量（微分IK核心）
        J_pinv = self.damped_pseudoinverse(J_combined)
        dq = gain * (J_pinv @ error_combined)

        # 7. 更新关节角度
        q_solution_full = self.q + dq

        # 8. 计算最终误差
        self.q = q_solution_full.copy()
        pin.forwardKinematics(self.model, self.data, self.q)
        pin.updateFramePlacements(self.model, self.data)

        elbow_placement_final = self.data.oMf[self.elbow_frame_id]
        wrist_placement_final = self.data.oMf[self.ee_frame_id]

        final_elbow_pos = elbow_placement_final.translation
        final_wrist_pos = wrist_placement_final.translation

        elbow_error = np.linalg.norm(target_elbow_pos - final_elbow_pos)
        wrist_error = np.linalg.norm(target_wrist_pos - final_wrist_pos)

        # 微分IK总是"成功"
        success = True

        # 只返回右臂的 7 个关节角度（后 7 个元素）
        q_solution = q_solution_full[7:]

        return q_solution, success, wrist_error, elbow_error

    def solve(self, target_pos, target_quat=None, q_init=None,
              position_only=True, gain=1.0):
        """
        微分IK求解：计算关节增量

        核心思想：Δq = J†(x_target - x_current)

        Args:
            target_pos: 目标位置 (3,)
            target_quat: 目标四元数 (4,) [x, y, z, w]，如果为None则只优化位置
            q_init: 初始关节角度 (7,) 右臂关节，如果为None则使用上次的q
            position_only: 是否只优化位置（忽略姿态）
            gain: 增益系数（0-1），控制每步移动的幅度

        Returns:
            q_solution: 求解的关节角度 (7,) 右臂关节
            success: 是否成功（微分IK总是成功）
            error: 位置误差（米）
        """
        # 1. 初始化
        if q_init is not None:
            # q_init 只有 7 个元素（右臂），需要扩展为 14 个元素（左臂+右臂）
            if len(q_init) == 7:
                # 前 7 个是左臂（保持为 0），后 7 个是右臂
                self.q = np.concatenate([np.zeros(7), q_init])
            else:
                self.q = q_init.copy()

        # 2. 计算当前末端位置
        pin.forwardKinematics(self.model, self.data, self.q)
        pin.updateFramePlacements(self.model, self.data)

        ee_placement = self.data.oMf[self.ee_frame_id]
        current_pos = ee_placement.translation

        # 3. 计算笛卡尔误差
        if position_only or target_quat is None:
            # 只优化位置（3-DoF）
            dx = target_pos - current_pos
            error_vector = dx
        else:
            # 优化位置+姿态（6-DoF）
            # 位置误差
            dx_pos = target_pos - current_pos

            # 姿态误差（使用对数映射）
            current_quat = pin.Quaternion(ee_placement.rotation)
            target_quat_pin = pin.Quaternion(target_quat[3], target_quat[0], target_quat[1], target_quat[2])

            # 计算姿态误差
            quat_error = target_quat_pin * current_quat.inverse()
            dx_ori = pin.log3(quat_error.matrix())

            # 组合误差
            error_vector = np.concatenate([dx_pos, dx_ori])

        # 4. 计算雅可比矩阵
        J_full = self.compute_jacobian(self.q)

        if position_only or target_quat is None:
            # 只使用位置部分的雅可比（前3行）
            J = J_full[:3, :]
        else:
            # 使用完整雅可比（6行）
            J = J_full

        # 5. 计算关节增量（微分IK核心）
        J_pinv = self.damped_pseudoinverse(J)
        dq = gain * (J_pinv @ error_vector)

        # 6. 更新关节角度
        q_solution_full = self.q + dq

        # 7. 计算最终误差
        self.q = q_solution_full.copy()
        pin.forwardKinematics(self.model, self.data, self.q)
        pin.updateFramePlacements(self.model, self.data)

        ee_placement_final = self.data.oMf[self.ee_frame_id]
        final_pos = ee_placement_final.translation
        pos_error = np.linalg.norm(target_pos - final_pos)

        # 微分IK总是"成功"（不需要收敛判断）
        success = True

        # 只返回右臂的 7 个关节角度（后 7 个元素）
        q_solution = q_solution_full[7:]

        return q_solution, success, pos_error

    def __del__(self):
        """清理临时文件"""
        if hasattr(self, 'temp_urdf'):
            try:
                os.unlink(self.temp_urdf.name)
            except:
                pass


if __name__ == "__main__":
    # 测试代码
    print("测试微分IK求解器...")

    solver = DifferentialIKSolver()

    # 测试目标
    target_pos = np.array([0.3, -0.1, 0.8])

    # 求解
    q_solution, success, error = solver.solve(target_pos)

    print(f"\n结果:")
    print(f"  成功: {success}")
    print(f"  误差: {error*1000:.2f}mm")
    print(f"  关节角度: {np.rad2deg(q_solution)}")
