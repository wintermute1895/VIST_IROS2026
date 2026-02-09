"""
VIST 控制器
封装 VIST 算法逻辑（纯算法，不涉及硬件）
"""

import numpy as np
import pinocchio as pin
from pathlib import Path

from src.core.motion_mapper import ArmMotionMapper
from src.core.ik_solver import PinocchioIKSolver
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.geometric_arm_solver import GeometricArmSolver
from src.control.safe_robot_controller import SafeRobotController


class VISTController:
    """VIST 算法控制器（纯算法逻辑）"""

    def __init__(self, config):
        """
        初始化 VIST 控制器

        Args:
            config: VISTConfig 配置对象
        """
        self.config = config

        # 1. 初始化运动映射器
        print("\n🗺️  初始化运动映射器...")
        self.mapper = ArmMotionMapper()
        print("✅ 运动映射器初始化完成")

        # 2. 初始化 IK 求解器
        print("\n🧠 初始化 IK 求解器...")
        project_root = Path(__file__).parent.parent.parent
        urdf_path = project_root / "config" / config.robot_model_urdf_file

        self.ik_solver = PinocchioIKSolver(
            urdf_path=str(urdf_path),
            end_effector_frame=config.robot_model_end_effector_frame
        )
        print("✅ IK 求解器初始化完成")

        # 3. 初始化 VIST 框架
        print("\n🔬 初始化 VIST 框架...")

        # 3.1 初始化几何求解器
        geometric_solver = None
        if config.vist_geometric_solver_enabled:
            print("   🧮 启用几何解析求解器...")
            geometric_solver = GeometricArmSolver(
                model=self.ik_solver.model,
                data=self.ik_solver.data,
                controlled_joints=self.ik_solver.controlled_indices,
                ee_frame_id=self.ik_solver.ee_frame_id,
                config=config
            )
            print(f"   ✅ 几何求解器初始化完成 (trust_weight={config.vist_geometric_solver_trust_weight})")

        # 3.2 初始化 VIST 卡尔曼滤波器
        self.vist_filter = VISTKalmanFilter(
            self.ik_solver,
            config,
            geometric_solver=geometric_solver
        )
        print("✅ VIST Kalman Filter 初始化完成")

        # 4. 初始化安全控制器
        print("\n🛡️  初始化安全控制器...")
        self.safety_controller = SafeRobotController(
            config=config,
            enable_logging=True
        )
        print("✅ 安全控制器初始化完成")

        # 初始化状态
        self.q_current = pin.neutral(self.ik_solver.model).copy()

    def process(self, human_keypoints):
        """
        处理人体关键点，计算安全的关节角度

        Args:
            human_keypoints: 人体关键点字典

        Returns:
            (q_safe, success, debug_info)
            - q_safe: 安全的关节角度 (7-DoF)
            - success: 是否成功
            - debug_info: 调试信息字典
        """
        debug_info = {}

        # 1. 运动映射
        result = self.mapper.human_to_robot(human_keypoints)
        if result is None:
            return None, False, {"error": "运动映射失败"}

        target_pos, target_quat, mapper_debug = result
        target_elbow = mapper_debug['elbow_pos']
        debug_info['target_pos'] = target_pos
        debug_info['target_elbow'] = target_elbow

        # 2. 工作空间检查（可选 - 几何解析解理论上总是在工作空间内）
        # 注意：由于motion mapper使用归一化重定向，target_pos应该总是在工作空间内
        # 这个检查主要用于调试，检测配置错误或坐标系不匹配
        shoulder_pos = self.config.robot_shoulder_position
        dist_to_shoulder = np.linalg.norm(target_pos - shoulder_pos)
        max_reach = self.config.robot_arm_lengths['upper'] + \
                    self.config.robot_arm_lengths['forearm']

        # 调试输出（仅在距离异常时打印）
        if dist_to_shoulder > max_reach * 0.98:  # 98%阈值用于调试
            print(f"⚠️ [工作空间检查] 距离接近极限")
            print(f"   肩部位置 (config): {shoulder_pos}")
            print(f"   肩部位置 (mapper): {self.mapper.P_base_shoulder}")
            print(f"   目标位置: {target_pos}")
            print(f"   距离: {dist_to_shoulder:.4f}m")
            print(f"   最大臂展: {max_reach:.4f}m")
            print(f"   使用率: {dist_to_shoulder/max_reach*100:.1f}%")

        # 放宽阈值到99%，避免误报（几何解析解理论上不会超出）
        if dist_to_shoulder > max_reach * 0.99:
            print(f"❌ [工作空间检查] 目标位置超出工作空间！")
            print(f"   这不应该发生 - 可能是配置错误或坐标系不匹配")
            return None, False, {"error": f"目标位置超出工作空间 ({dist_to_shoulder:.3f}m > {max_reach*0.99:.3f}m)"}

        # 3. VIST 卡尔曼滤波求解
        q_solution, success, error = self.vist_filter.solve(
            target_pos=target_pos,
            target_quat=target_quat,
            q_init=self.q_current,
            elbow_pos=target_elbow,
            shoulder_pos=shoulder_pos
        )

        if not success:
            return None, False, {"error": f"VIST 求解失败 (误差={error*1000:.2f}mm)"}

        debug_info['ik_error'] = error

        # 4. 安全控制器检查
        q_safe, safety_status = self.safety_controller.process_command(q_solution)
        debug_info['safety_status'] = safety_status

        # 检查紧急停止
        if safety_status['emergency_stop']:
            return None, False, {"error": "紧急停止激活"}

        # 5. 更新状态
        # 扩展到完整模型维度
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(q_safe) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_safe[i]
        self.q_current = q_full

        return q_safe, True, debug_info

    def get_safety_statistics(self):
        """获取安全控制统计信息"""
        return self.safety_controller.get_statistics()

    def reset(self):
        """重置控制器状态"""
        self.q_current = pin.neutral(self.ik_solver.model).copy()
        self.safety_controller.reset()
