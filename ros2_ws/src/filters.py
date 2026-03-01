"""
遥操作滤波器策略模式实现
包含基类、5种算法适配器和工厂类
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import numpy as np

# 导入核心算法模块
from src.core.one_euro_filter import OneEuroFilter
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver as IKSolver
from src.core.tcp_compensation import TCPCompensation
from src.core.intent_detector import ContinuousIntentDetector as IntentDetector
from src.core.vitual_fixture_fsm import VirtualFixtureFSM  # 使用新的相对增量映射版本
from src.core.apf_filter import APFCore


# ==================== 辅助函数：双臂模型适配 ====================

def expand_single_arm_to_dual(q_single: np.ndarray, arm_side: str = 'left') -> np.ndarray:
    """
    将单臂7关节扩展为双臂14关节向量

    Args:
        q_single: 单臂关节角 [7]
        arm_side: 'left' 或 'right'

    Returns:
        双臂关节角 [14]
    """
    q_dual = np.zeros(14)
    if arm_side == 'left':
        q_dual[0:7] = q_single
    else:  # right
        q_dual[7:14] = q_single
    return q_dual


class BaseTeleopFilter(ABC):
    """遥操作滤波器抽象基类"""

    def __init__(self,
                 ik_solver: IKSolver,
                 tcp_compensation: TCPCompensation,
                 target_pose: Optional[np.ndarray] = None,
                 **kwargs):
        """
        初始化滤波器基类

        Args:
            ik_solver: 逆运动学求解器实例
            tcp_compensation: 工具端补偿实例
            target_pose: 目标位姿 [x, y, z, rx, ry, rz]（用于装配任务）
            **kwargs: 其他算法特定参数
        """
        self.ik_solver = ik_solver
        self.tcp_compensation = tcp_compensation
        self.target_pose = target_pose if target_pose is not None else np.zeros(6)
        self.last_output = None

    @abstractmethod
    def update(self, q_in: List[float], dt: float) -> List[float]:
        """
        滤波器更新接口

        Args:
            q_in: 输入关节角度列表 [q1, q2, ..., q7]
            dt: 时间步长（秒）

        Returns:
            输出关节角度列表
        """
        pass

    def reset(self):
        """重置滤波器状态（可选实现）"""
        self.last_output = None


class GELLOFilter(BaseTeleopFilter):
    """GELLO 直通策略（无滤波）"""

    def update(self, q_in: List[float], dt: float) -> List[float]:
        """直接返回输入，不做任何处理"""
        return q_in


class OneEuroTeleopFilter(BaseTeleopFilter):
    """1-Euro 滤波策略"""

    def __init__(self,
                 ik_solver: IKSolver,
                 tcp_compensation: TCPCompensation,
                 target_pose: Optional[np.ndarray] = None,
                 min_cutoff: float = 1.0,
                 beta: float = 0.007,
                 **kwargs):
        """
        初始化 1-Euro 滤波器

        Args:
            min_cutoff: 最小截止频率
            beta: 速度系数
        """
        super().__init__(ik_solver, tcp_compensation, target_pose, **kwargs)

        # 为每个关节创建独立的 1-Euro 滤波器
        self.filters = [
            OneEuroFilter(min_cutoff=min_cutoff, beta=beta)
            for _ in range(7)  # 假设7自由度机械臂
        ]

    def update(self, q_in: List[float], dt: float) -> List[float]:
        """应用 1-Euro 滤波"""
        q_out = []
        for i, (q_val, filter_obj) in enumerate(zip(q_in, self.filters)):
            filtered_val = filter_obj(q_val)  # 使用 __call__ 方法
            q_out.append(filtered_val)
        return q_out

    def reset(self):
        """重置所有滤波器"""
        super().reset()
        for f in self.filters:
            f.reset()


class VISTTeleopFilter(BaseTeleopFilter):
    """VIST 卡尔曼滤波策略"""

    def __init__(self,
                 ik_solver: IKSolver,
                 tcp_compensation: TCPCompensation,
                 target_pose: Optional[np.ndarray] = None,
                 vist_config=None,
                 geometric_solver=None,
                 **kwargs):
        """
        初始化 VIST 滤波器

        Args:
            vist_config: VIST 配置对象（从 ROS 节点传入）
            geometric_solver: 几何求解器（可选）
        """
        super().__init__(ik_solver, tcp_compensation, target_pose, **kwargs)

        # 实例化 VIST 核心算法（需要完整的配置对象）
        if vist_config is None:
            raise ValueError("VIST 滤波器需要 vist_config 参数")

        self.vist_filter = VISTKalmanFilter(
            ik_solver=ik_solver,
            config=vist_config,
            geometric_solver=geometric_solver
        )

        self.previous_target_pos = None

    def update(self, q_in: List[float], dt: float) -> List[float]:
        """
        应用 VIST 卡尔曼滤波

        VIST 需要目标位置来计算微分 IK，这里使用固定目标位姿
        """
        # 使用目标位姿作为输入
        target_pos = self.target_pose[:3]
        target_quat = None  # 简化版本，暂不使用姿态

        # 调用 VIST 更新（返回估计的关节角度）
        q_solution, success = self.vist_filter.update(
            target_pos=target_pos,
            target_quat=target_quat,
            human_delta_theta=None,  # 让 VIST 自动计算
            previous_target_pos=self.previous_target_pos
        )

        # 更新上一帧目标位置
        self.previous_target_pos = target_pos.copy()

        # 返回估计结果
        return q_solution.tolist() if success else q_in

    def reset(self):
        """重置卡尔曼滤波器"""
        super().reset()
        self.previous_target_pos = None
        # VIST 滤波器会在下次更新时自动重置


class FSMTeleopFilter(BaseTeleopFilter):
    """
    虚拟夹具有限状态机策略（关节空间版本）

    实现基于圆柱形结界的双状态关节角缩放控制：
    - 自由态（D > R）：1:1 关节角增量跟随（基于全局锚点）
    - 粘滞态（D ≤ R）：关节角缩放（如 1:5）

    核心特性：
    - 全局锚点机制：启动时立即记录，消除启动抖动
    - 关节空间相对增量映射：禁止绝对映射
    - 圆柱形结界判定：通过正运动学计算法兰位置
    - NO IK：全程在关节空间操作，无需逆运动学
    """

    def __init__(self,
                 ik_solver: IKSolver,
                 tcp_compensation: TCPCompensation,
                 target_pose: Optional[np.ndarray] = None,
                 socket_center_xy: Optional[List[float]] = None,
                 cylinder_radius: float = 0.05,
                 xy_scale_factor: float = 0.2,
                 z_scale_factor: float = 1.0,
                 arm_side: str = 'left',
                 **kwargs):
        """
        初始化虚拟夹具 FSM 滤波器

        Args:
            ik_solver: 逆运动学求解器实例（仅用于正运动学）
            tcp_compensation: 工具端补偿实例
            target_pose: 目标位姿 [x, y, z, rx, ry, rz]（用于兼容性，实际使用 socket_center_xy）
            socket_center_xy: 插座中心的 XY 坐标 [x, y] (单位: m)
            cylinder_radius: 圆柱形结界半径 (单位: m)
            xy_scale_factor: 粘滞态下的 XY 轴缩放比例 (默认 0.2，即 1:5) - 已废弃
            z_scale_factor: 粘滞态下的 Z 轴缩放比例 (默认 1.0，即 1:1) - 已废弃
            arm_side: 控制的机械臂侧 ('left' 或 'right')
        """
        super().__init__(ik_solver, tcp_compensation, target_pose, **kwargs)

        # 如果没有提供 socket_center_xy，使用 target_pose 的 XY 坐标
        if socket_center_xy is None:
            socket_center_xy = self.target_pose[:2].tolist()

        # 实例化虚拟夹具 FSM 核心（关节空间版本）
        # 注意：xy_scale_factor 和 z_scale_factor 在关节空间版本中统一为 joint_scale_factor
        joint_scale_factor = xy_scale_factor  # 使用 xy_scale_factor 作为关节角缩放因子

        self.virtual_fixture_fsm = VirtualFixtureFSM(
            socket_center_xy=socket_center_xy,
            cylinder_radius=cylinder_radius,
            joint_scale_factor=joint_scale_factor
        )

        # 机械臂侧配置
        self.arm_side = arm_side

    def update(self, q_in: List[float], dt: float, robot_flange_pose: Optional[np.ndarray] = None) -> List[float]:
        """
        虚拟夹具 FSM 完整逻辑流程（关节空间版本，NO IK）：
        1. 正运动学：计算机械臂当前法兰位置
        2. FSM 更新：基于圆柱形结界判定状态，计算目标关节角（关节空间增量映射）
        3. 输出：目标关节角（无需 IK）

        Args:
            q_in: 输入关节角度列表 [q1, q2, ..., q7] (单臂 7 个关节)
            dt: 时间步长（秒）
            robot_flange_pose: 机械臂当前法兰位姿 [x, y, z, rx, ry, rz]（可选）
                              如果提供，则使用外部 SDK 的 FK 结果
                              如果不提供，则使用输入关节角计算

        Returns:
            输出关节角度列表 (单臂 7 个关节)
        """
        try:
            import pinocchio as pin

            # ========== Step 1: 正运动学 - 计算机械臂当前法兰位置 ==========
            # 将 7 维单臂关节角扩展为 14 维双臂关节角（适配双臂 URDF）
            q_array = np.array(q_in)
            q_dual = expand_single_arm_to_dual(q_array, self.arm_side)

            # 执行正运动学
            pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_dual)
            pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

            # 获取机械臂法兰位置
            if robot_flange_pose is not None:
                # 使用外部提供的机械臂法兰位姿（推荐方式）
                robot_flange_position = robot_flange_pose[:3]
            else:
                # 使用输入关节角计算法兰位置
                robot_flange_position = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id].translation.copy()

            # ========== Step 2: 虚拟夹具 FSM 更新（关节空间增量映射，NO IK） ==========
            # 调用 FSM 核心算法，获取目标关节角和当前状态
            target_joints, current_state = self.virtual_fixture_fsm.update(
                exo_joints=q_array,
                robot_flange_position=robot_flange_position
            )

            # ========== Step 3: 输出目标关节角（无需 IK） ==========
            self.last_output = target_joints.tolist()
            return target_joints.tolist()

        except Exception as e:
            # 发生错误时，抛出异常让上层处理
            import traceback
            error_msg = f"[FSM Error] {e}\nTraceback: {traceback.format_exc()}"
            print(error_msg)  # 同时打印到标准输出
            raise RuntimeError(error_msg) from e

    def reset(self):
        """重置滤波器状态"""
        super().reset()
        self.virtual_fixture_fsm.reset()

    def get_state_info(self) -> dict:
        """
        获取 FSM 状态信息（用于调试和可视化）

        Returns:
            状态信息字典
        """
        return self.virtual_fixture_fsm.get_state_info()


class APFTeleopFilter(BaseTeleopFilter):
    """人工势场策略"""

    def __init__(self,
                 ik_solver: IKSolver,
                 tcp_compensation: TCPCompensation,
                 target_pose: Optional[np.ndarray] = None,
                 obstacle_positions: Optional[List[np.ndarray]] = None,
                 attractive_gain: float = 1.0,
                 repulsive_gain: float = 0.5,
                 **kwargs):
        """
        初始化 APF 滤波器

        Args:
            obstacle_positions: 障碍物位置列表
            attractive_gain: 引力增益
            repulsive_gain: 斥力增益
        """
        super().__init__(ik_solver, tcp_compensation, target_pose, **kwargs)

        # 实例化APF核心
        self.apf_core = APFCore(
            attractive_gain=attractive_gain,
            repulsive_gain=repulsive_gain
        )

        # 障碍物列表
        self.obstacle_positions = obstacle_positions if obstacle_positions else []

    def update(self, q_in: List[float], dt: float) -> List[float]:
        """
        APF 完整逻辑流程：
        1. 正运动学求解当前位姿
        2. 计算引力和斥力
        3. 合成总虚拟力
        4. 将力转换为目标位姿增量
        5. 逆运动学求解输出关节角
        """
        # Step 1: 正运动学 - 获取当前末端位置
        import pinocchio as pin
        q_array = np.array(q_in)
        pin.forwardKinematics(self.ik_solver.model, self.ik_solver.data, q_array)
        pin.updateFramePlacements(self.ik_solver.model, self.ik_solver.data)

        # 获取末端位置
        current_pos = self.ik_solver.data.oMf[self.ik_solver.ee_frame_id].translation.copy()
        current_pose = np.concatenate([current_pos, np.zeros(3)])  # [x,y,z,rx,ry,rz]

        # Step 2: 计算引力（指向目标）
        attractive_force = self._calc_attractive_force(current_pos)

        # Step 3: 计算斥力（远离障碍物）
        repulsive_force = self._calc_repulsive_force(current_pos)

        # Step 4: 合成总虚拟力
        total_force = attractive_force + repulsive_force

        # Step 5: 将虚拟力转换为位姿调整量
        target_pose_adjusted = self._apply_force_to_pose(
            current_pose=current_pose,
            force=total_force,
            dt=dt
        )

        # Step 6: 应用TCP补偿（将TCP位姿转换为法兰盘位姿）
        target_pos = target_pose_adjusted[:3]
        target_quat = None  # 简化版本，暂不处理姿态
        flange_pos, _ = self.tcp_compensation.compensate_target_pose(target_pos, target_quat)

        # Step 7: 逆运动学求解（使用 IKSolver 的 solve 方法）
        q_solution, success, error = self.ik_solver.solve(
            target_pos=flange_pos,
            target_quat=target_quat,
            q_init=q_in
        )

        # 返回求解结果
        return q_solution.tolist() if success else q_in

    def _calc_attractive_force(self, current_position: np.ndarray) -> np.ndarray:
        """
        计算目标引力
        调用APF核心算法
        """
        target_position = self.target_pose[:3]
        return self.apf_core.compute_attractive_force(current_position, target_position)

    def _calc_repulsive_force(self, current_position: np.ndarray) -> np.ndarray:
        """
        计算障碍物斥力
        调用APF核心算法
        """
        if not self.obstacle_positions:
            return np.zeros(3)

        return self.apf_core.compute_repulsive_force(current_position, self.obstacle_positions)

    def _apply_force_to_pose(self,
                             current_pose: np.ndarray,
                             force: np.ndarray,
                             dt: float) -> np.ndarray:
        """
        将虚拟力转换为目标位姿
        调用APF核心算法
        """
        return self.apf_core.apply_force_to_pose(current_pose, force, dt)

    def add_obstacle(self, position: np.ndarray):
        """动态添加障碍物"""
        self.obstacle_positions.append(position)

    def clear_obstacles(self):
        """清除所有障碍物"""
        self.obstacle_positions.clear()


class FilterFactory:
    """滤波器工厂类"""

    @staticmethod
    def create_filter(filter_type: str, **kwargs) -> BaseTeleopFilter:
        """
        根据类型字符串创建对应的滤波器实例

        Args:
            filter_type: 滤波器类型 ('gello', 'oneeuro', 'vist', 'fsm', 'apf')
            **kwargs: 传递给滤波器构造函数的参数

        Returns:
            滤波器实例

        Raises:
            ValueError: 不支持的滤波器类型
        """
        filter_map = {
            'gello': GELLOFilter,
            'oneeuro': OneEuroTeleopFilter,
            'vist': VISTTeleopFilter,
            'fsm': FSMTeleopFilter,
            'apf': APFTeleopFilter
        }

        filter_class = filter_map.get(filter_type.lower())
        if filter_class is None:
            raise ValueError(
                f"不支持的滤波器类型: {filter_type}. "
                f"可用类型: {list(filter_map.keys())}"
            )

        return filter_class(**kwargs)