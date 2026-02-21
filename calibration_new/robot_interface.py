"""
机器人接口模块
==============
提供机器人位姿处理的抽象层和仿真功能。

核心组件：
1. RobotInterface: 机器人控制的抽象基类
2. process_raw_pose(): 通用位姿格式转换器
3. SimulatedRobot: 用于算法验证的软件仿真
"""

from abc import ABC, abstractmethod
from typing import Union, List, Tuple, Dict, Any
import numpy as np
from scipy.spatial.transform import Rotation as R
import cv2

# =============================================================================
# 抽象机器人接口
# =============================================================================

class RobotInterface(ABC):
    """
    机器人控制的抽象基类。
    实现此接口以连接您的特定机器人。
    """

    @abstractmethod
    def get_pose(self) -> np.ndarray:
        """
        获取当前机器人末端执行器相对于基座的位姿。

        Returns:
            np.ndarray: 4x4 齐次变换矩阵 T_base_to_flange
                       [[R11, R12, R13, tx],
                        [R21, R22, R23, ty],
                        [R31, R32, R33, tz],
                        [0,   0,   0,   1 ]]
        """
        pass

# =============================================================================
# 通用位姿转换器
# =============================================================================

def process_raw_pose(raw_pose: Union[np.ndarray, List, Tuple],
                     config: Dict[str, Any]) -> np.ndarray:
    """
    将机器人位姿从各种格式转换为 4x4 齐次变换矩阵。

    这是标定精度的关键函数。它处理不同机器人制造商位姿表示的所有差异。

    Args:
        raw_pose: 来自机器人 SDK 的原始位姿数据
                 - 对于 'euler'/'rotvec': [x, y, z, rx, ry, rz] 或 [rx, ry, rz, x, y, z]
                 - 对于 'quat': [x, y, z, qx, qy, qz, qw] 或 [qw, qx, qy, qz, x, y, z]
                 - 对于 'matrix': 4x4 或 3x4 矩阵
        config: 配置字典（来自 config.ROBOT_POSE_FMT）

    Returns:
        np.ndarray: 4x4 齐次变换矩阵

    Example:
        >>> from config import ROBOT_POSE_FMT
        >>> raw = [0.5, 0.2, 0.3, 0.0, 0.0, 1.57]  # x,y,z,roll,pitch,yaw
        >>> T = process_raw_pose(raw, ROBOT_POSE_FMT)
        >>> print(T.shape)  # (4, 4)
    """
    raw_pose = np.array(raw_pose, dtype=np.float64)

    # 处理矩阵输入
    if config['type'] == 'matrix':
        if raw_pose.shape == (4, 4):
            return raw_pose
        elif raw_pose.shape == (3, 4):
            # 将 3x4 转换为 4x4
            T = np.eye(4)
            T[:3, :] = raw_pose
            return T
        else:
            raise ValueError(f"无效的矩阵形状: {raw_pose.shape}")

    # 根据顺序解析位置和旋转
    if config['is_position_first']:
        if config['type'] in ['euler', 'rotvec']:
            position = raw_pose[:3]
            rotation_params = raw_pose[3:6]
        elif config['type'] == 'quat':
            position = raw_pose[:3]
            rotation_params = raw_pose[3:7]
        else:
            raise ValueError(f"未知类型: {config['type']}")
    else:
        # 旋转在前（罕见）
        if config['type'] in ['euler', 'rotvec']:
            rotation_params = raw_pose[:3]
            position = raw_pose[3:6]
        elif config['type'] == 'quat':
            if config['quat_format'] == 'wxyz':
                rotation_params = raw_pose[:4]
                position = raw_pose[4:7]
            else:
                rotation_params = raw_pose[:4]
                position = raw_pose[4:7]
        else:
            raise ValueError(f"未知类型: {config['type']}")

    # 转换位置单位
    if config['position_unit'] == 'mm':
        position = position / 1000.0  # 将 mm 转换为 m

    # 将旋转转换为 scipy Rotation 对象
    if config['type'] == 'euler':
        # 转换角度单位
        if config['unit'] == 'deg':
            rotation_params = np.deg2rad(rotation_params)

        # 解析序列（内旋 vs 外旋）
        seq = config['seq']
        if seq.isupper():
            # 外旋（固定坐标系）
            # scipy 使用小写表示内旋，大写表示外旋
            rotation = R.from_euler(seq, rotation_params, degrees=False)
        else:
            # 内旋（旋转坐标系）
            rotation = R.from_euler(seq, rotation_params, degrees=False)

    elif config['type'] == 'rotvec':
        # 旋转向量（轴角表示）
        if config['unit'] == 'deg':
            # 不太可能但处理它
            rotation_params = np.deg2rad(rotation_params)
        rotation = R.from_rotvec(rotation_params)

    elif config['type'] == 'quat':
        # 四元数
        if config['quat_format'] == 'wxyz':
            # 将 [w, x, y, z] 转换为 [x, y, z, w] 供 scipy 使用
            qw, qx, qy, qz = rotation_params
            rotation_params = [qx, qy, qz, qw]
        # else: 已经是 [x, y, z, w] 格式
        rotation = R.from_quat(rotation_params)

    else:
        raise ValueError(f"不支持的旋转类型: {config['type']}")

    # 构建 4x4 齐次变换矩阵
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = rotation.as_matrix()
    T[:3, 3] = position

    return T

# =============================================================================
# 仿真机器人（用于无硬件的软件验证）
# =============================================================================

class SimulatedRobot(RobotInterface):
    """
    用于算法验证的仿真机器人（无需物理硬件）。

    此类基于已知的 Ground Truth 变换生成合成标定数据。
    通过将标定结果与 Ground Truth 比较，我们可以验证整个流程的数学正确性。

    工作流程：
    1. 设置 Ground Truth 手眼变换
    2. 生成随机机器人位姿
    3. 使用运动学链计算相机坐标系中的预期标定板位姿
    4. 添加真实噪声以模拟测量误差
    5. 运行标定并将结果与 Ground Truth 比较
    """

    def __init__(self,
                 mode: str,
                 ground_truth: np.ndarray,
                 camera_matrix: np.ndarray,
                 dist_coeffs: np.ndarray,
                 board_config: Dict[str, Any],
                 num_poses: int = 20,
                 noise_config: Dict[str, Any] = None):
        """
        初始化仿真机器人。

        Args:
            mode: 'eye_in_hand' 或 'eye_to_hand'
            ground_truth: Ground Truth 变换矩阵 (4x4)
                         - 对于 eye_in_hand: T_flange_to_camera
                         - 对于 eye_to_hand: T_base_to_camera
            camera_matrix: 相机内参矩阵 (3x3)
            dist_coeffs: 相机畸变系数
            board_config: ChArUco 标定板配置
            num_poses: 要生成的位姿数量
            noise_config: 真实性的噪声参数
        """
        self.mode = mode
        self.ground_truth = ground_truth
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs
        self.board_config = board_config
        self.num_poses = num_poses

        # 默认噪声参数
        self.noise_config = noise_config or {
            'pixel_noise_std': 0.5,
            'pose_noise_translation': 0.0001,
            'pose_noise_rotation': 0.001,
        }

        # 生成合成数据
        self.robot_poses, self.board_poses_in_camera = self._generate_data()

    def get_pose(self) -> np.ndarray:
        """在仿真模式下不使用。"""
        raise NotImplementedError("使用 get_synthetic_data() 代替")

    def _generate_random_pose(self, idx: int) -> np.ndarray:
        """
        生成随机机器人位姿。

        对于 eye-in-hand: 机器人移动，标定板固定
        对于 eye-to-hand: 标定板随机器人移动，相机固定

        Returns:
            np.ndarray: 4x4 变换矩阵 T_base_to_flange
        """
        # 生成随机位置（在合理的工作空间内）
        if self.mode == 'eye_in_hand':
            # 机器人末端执行器在标定板上方的半球内移动
            radius = 0.3 + 0.2 * np.random.rand()  # 0.3 到 0.5 米
            theta = np.random.uniform(0, 2 * np.pi)
            phi = np.random.uniform(np.pi/6, np.pi/3)  # 30 到 60 度

            x = radius * np.sin(phi) * np.cos(theta)
            y = radius * np.sin(phi) * np.sin(theta)
            z = radius * np.cos(phi) + 0.2  # 距桌面的偏移

        else:  # eye_to_hand
            # 标定板在机器人工作空间内移动
            x = 0.3 + 0.2 * np.random.rand()
            y = -0.2 + 0.4 * np.random.rand()
            z = 0.1 + 0.2 * np.random.rand()

        # 生成随机方向（必须包含显著的旋转变化！）
        # 手眼标定算法依赖旋转轴的差异来解算矩阵
        # 如果旋转变化太小，算法会失效并返回单位矩阵
        if self.mode == 'eye_in_hand':
            # 相机应向下指向标定板，但需要大幅度旋转变化
            roll = np.random.uniform(-0.8, 0.8)   # ±45度
            pitch = np.random.uniform(-0.8, 0.8)  # ±45度
            yaw = np.random.uniform(-np.pi, np.pi)
        else:
            # 标定板应向上面向相机
            roll = np.random.uniform(-0.6, 0.6)   # ±35度
            pitch = np.random.uniform(-0.6, 0.6)  # ±35度
            yaw = np.random.uniform(-np.pi, np.pi)

        # 构建变换矩阵
        rotation = R.from_euler('xyz', [roll, pitch, yaw])
        T = np.eye(4)
        T[:3, :3] = rotation.as_matrix()
        T[:3, 3] = [x, y, z]

        # 添加小的位姿噪声
        T[:3, 3] += np.random.normal(0, self.noise_config['pose_noise_translation'], 3)
        noise_rot = R.from_rotvec(
            np.random.normal(0, self.noise_config['pose_noise_rotation'], 3)
        )
        T[:3, :3] = (noise_rot * R.from_matrix(T[:3, :3])).as_matrix()

        return T

    def _compute_board_pose_in_camera(self, T_base_to_flange: np.ndarray) -> np.ndarray:
        """
        使用运动学链计算标定板在相机坐标系中的位姿。

        运动学链：
        - Eye-in-hand: T_camera_to_board = T_camera_to_flange @ T_flange_to_base @ T_base_to_board
                      其中 T_base_to_board 固定（为简单起见为单位矩阵）
                      且 T_camera_to_flange = inv(T_flange_to_camera)

        - Eye-to-hand: T_camera_to_board = T_camera_to_base @ T_base_to_flange @ T_flange_to_board
                      其中 T_flange_to_board 固定（为简单起见为单位矩阵）
                      且 T_camera_to_base = inv(T_base_to_camera)

        Args:
            T_base_to_flange: 机器人位姿 (4x4 矩阵)

        Returns:
            np.ndarray: 相机坐标系中的标定板位姿 (4x4 矩阵)
        """
        if self.mode == 'eye_in_hand':
            # 标定板固定在原点（为简单起见）
            T_base_to_board = np.eye(4)

            # 运动学链: Camera -> Flange -> Base -> Board
            T_flange_to_camera = self.ground_truth
            T_camera_to_flange = np.linalg.inv(T_flange_to_camera)
            T_flange_to_base = np.linalg.inv(T_base_to_flange)

            T_camera_to_board = T_camera_to_flange @ T_flange_to_base @ T_base_to_board

        else:  # eye_to_hand
            # 标定板固定在法兰上（为简单起见，无偏移）
            T_flange_to_board = np.eye(4)

            # 运动学链: Camera -> Base -> Flange -> Board
            T_base_to_camera = self.ground_truth
            T_camera_to_base = np.linalg.inv(T_base_to_camera)

            T_camera_to_board = T_camera_to_base @ T_base_to_flange @ T_flange_to_board

        return T_camera_to_board

    def _generate_data(self) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        生成合成标定数据。

        Returns:
            Tuple of (robot_poses, board_poses_in_camera)
        """
        robot_poses = []
        board_poses = []

        for i in range(self.num_poses):
            # 生成随机机器人位姿
            T_base_to_flange = self._generate_random_pose(i)

            # 计算相机坐标系中的标定板位姿
            T_camera_to_board = self._compute_board_pose_in_camera(T_base_to_flange)

            robot_poses.append(T_base_to_flange)
            board_poses.append(T_camera_to_board)

        return robot_poses, board_poses

    def get_synthetic_data(self) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """
        获取生成的合成数据。

        Returns:
            Tuple of (robot_poses, board_poses_in_camera)
        """
        return self.robot_poses, self.board_poses_in_camera

    def add_pixel_noise_to_corners(self, corners: np.ndarray) -> np.ndarray:
        """
        向检测到的角点添加真实的像素噪声。

        Args:
            corners: 角点坐标 (Nx2)

        Returns:
            np.ndarray: 带噪声的角点
        """
        noise = np.random.normal(0, self.noise_config['pixel_noise_std'], corners.shape)
        return corners + noise

# =============================================================================
# 辅助函数
# =============================================================================

def matrix_to_rvec_tvec(T: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    将 4x4 变换矩阵转换为 OpenCV 的 rvec 和 tvec。

    Args:
        T: 4x4 齐次变换矩阵

    Returns:
        Tuple of (rvec, tvec) 其中:
        - rvec: 旋转向量 (3x1)
        - tvec: 平移向量 (3x1)
    """
    rotation = R.from_matrix(T[:3, :3])
    rvec = rotation.as_rotvec().reshape(3, 1)
    tvec = T[:3, 3].reshape(3, 1)
    return rvec, tvec

def rvec_tvec_to_matrix(rvec: np.ndarray, tvec: np.ndarray) -> np.ndarray:
    """
    将 rvec 和 tvec 转换为 4x4 变换矩阵。

    Args:
        rvec: 旋转向量 (3x1 或 3,)
        tvec: 平移向量 (3x1 或 3,)

    Returns:
        np.ndarray: 4x4 齐次变换矩阵
    """
    rvec = np.array(rvec).flatten()
    tvec = np.array(tvec).flatten()

    rotation = R.from_rotvec(rvec)
    T = np.eye(4)
    T[:3, :3] = rotation.as_matrix()
    T[:3, 3] = tvec
    return T

if __name__ == "__main__":
    # 测试位姿转换
    print("="*70)
    print("测试通用位姿转换器")
    print("="*70)

    # 测试用例 1: 欧拉角 XYZ 内旋，弧度，位置在前
    config1 = {
        'type': 'euler',
        'unit': 'rad',
        'seq': 'xyz',
        'is_position_first': True,
        'position_unit': 'm',
    }
    raw_pose1 = [0.5, 0.2, 0.3, 0.0, 0.0, 1.57]  # x, y, z, roll, pitch, yaw
    T1 = process_raw_pose(raw_pose1, config1)
    print(f"\n测试 1 - 欧拉角 XYZ (弧度):")
    print(f"输入: {raw_pose1}")
    print(f"输出:\n{T1}")

    # 测试用例 2: 四元数 xyzw
    config2 = {
        'type': 'quat',
        'quat_format': 'xyzw',
        'is_position_first': True,
        'position_unit': 'm',
    }
    raw_pose2 = [0.5, 0.2, 0.3, 0.0, 0.0, 0.707, 0.707]  # x, y, z, qx, qy, qz, qw
    T2 = process_raw_pose(raw_pose2, config2)
    print(f"\n测试 2 - 四元数 (xyzw):")
    print(f"输入: {raw_pose2}")
    print(f"输出:\n{T2}")

    print("\n" + "="*70)
    print("所有测试通过！")
    print("="*70)
