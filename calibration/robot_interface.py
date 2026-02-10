"""
Robot Interface - 机械臂接口抽象类
用户需要根据自己的机械臂 SDK 实现此接口
"""

from abc import ABC, abstractmethod
import numpy as np
from scipy.spatial.transform import Rotation as R


class RobotInterface(ABC):
    """
    机械臂接口抽象类
    用户需要继承此类并实现具体的机械臂控制方法
    """

    @abstractmethod
    def get_current_pose(self) -> np.ndarray:
        """
        获取当前机械臂末端执行器（End-Effector）相对于基座（Base）的位姿

        Returns:
            np.ndarray: 4x4 齐次变换矩阵 (Homogeneous Transformation Matrix)
                       表示从 Base 到 End-Effector 的变换 (T_base_to_end)

                       格式：
                       [[R11, R12, R13, tx],
                        [R21, R22, R23, ty],
                        [R31, R32, R33, tz],
                        [0,   0,   0,   1 ]]

                       其中：
                       - R (3x3): 旋转矩阵
                       - t (3x1): 平移向量 [tx, ty, tz]（单位：米）

        注意：
            1. 如果你的机械臂 SDK 返回的是 [x, y, z, rx, ry, rz] 格式：
               - x, y, z: 位置（米）
               - rx, ry, rz: 旋转（可能是欧拉角、轴角等）
               请使用下面的辅助函数转换为 4x4 矩阵

            2. 如果你的机械臂 SDK 返回的是四元数 [x, y, z, qx, qy, qz, qw]：
               请使用 quaternion_to_matrix() 辅助函数
        """
        pass

    @abstractmethod
    def move_to(self, target_pose: np.ndarray) -> bool:
        """
        移动机械臂到指定位姿（可选实现，用于自动化采集）

        Args:
            target_pose: 4x4 齐次变换矩阵，目标位姿

        Returns:
            bool: 是否移动成功
        """
        pass

    # ==================== 辅助函数：坐标转换 ====================

    @staticmethod
    def pose_to_matrix(x: float, y: float, z: float,
                       rx: float, ry: float, rz: float,
                       rotation_type: str = "euler_xyz") -> np.ndarray:
        """
        将位姿参数转换为 4x4 齐次变换矩阵

        Args:
            x, y, z: 位置（米）
            rx, ry, rz: 旋转参数
            rotation_type: 旋转表示类型
                - "euler_xyz": 欧拉角 XYZ 顺序（弧度）
                - "euler_zyx": 欧拉角 ZYX 顺序（弧度）
                - "rotvec": 旋转向量（轴角表示，弧度）

        Returns:
            np.ndarray: 4x4 齐次变换矩阵
        """
        # 创建旋转对象
        if rotation_type == "euler_xyz":
            rotation = R.from_euler('xyz', [rx, ry, rz], degrees=False)
        elif rotation_type == "euler_zyx":
            rotation = R.from_euler('zyx', [rx, ry, rz], degrees=False)
        elif rotation_type == "rotvec":
            rotation = R.from_rotvec([rx, ry, rz])
        else:
            raise ValueError(f"不支持的旋转类型: {rotation_type}")

        # 获取旋转矩阵
        rotation_matrix = rotation.as_matrix()

        # 构建 4x4 齐次变换矩阵
        transform_matrix = np.eye(4)
        transform_matrix[:3, :3] = rotation_matrix
        transform_matrix[:3, 3] = [x, y, z]

        return transform_matrix

    @staticmethod
    def quaternion_to_matrix(x: float, y: float, z: float,
                            qx: float, qy: float, qz: float, qw: float) -> np.ndarray:
        """
        将位置+四元数转换为 4x4 齐次变换矩阵

        Args:
            x, y, z: 位置（米）
            qx, qy, qz, qw: 四元数（注意顺序：有些 SDK 是 [qw, qx, qy, qz]）

        Returns:
            np.ndarray: 4x4 齐次变换矩阵
        """
        # 创建旋转对象（scipy 使用 [x, y, z, w] 顺序）
        rotation = R.from_quat([qx, qy, qz, qw])
        rotation_matrix = rotation.as_matrix()

        # 构建 4x4 齐次变换矩阵
        transform_matrix = np.eye(4)
        transform_matrix[:3, :3] = rotation_matrix
        transform_matrix[:3, 3] = [x, y, z]

        return transform_matrix

    @staticmethod
    def matrix_to_pose(matrix: np.ndarray, rotation_type: str = "euler_xyz") -> tuple:
        """
        将 4x4 齐次变换矩阵转换为位姿参数

        Args:
            matrix: 4x4 齐次变换矩阵
            rotation_type: 旋转表示类型（同 pose_to_matrix）

        Returns:
            tuple: (x, y, z, rx, ry, rz)
        """
        x, y, z = matrix[:3, 3]
        rotation = R.from_matrix(matrix[:3, :3])

        if rotation_type == "euler_xyz":
            rx, ry, rz = rotation.as_euler('xyz', degrees=False)
        elif rotation_type == "euler_zyx":
            rx, ry, rz = rotation.as_euler('zyx', degrees=False)
        elif rotation_type == "rotvec":
            rx, ry, rz = rotation.as_rotvec()
        else:
            raise ValueError(f"不支持的旋转类型: {rotation_type}")

        return x, y, z, rx, ry, rz

    @staticmethod
    def lbot_pose_to_matrix(position, euler) -> np.ndarray:
        """
        将 LBot SDK 的位姿数据转换为 4x4 齐次变换矩阵

        这是专门为 LBot 机械臂 SDK 设计的辅助函数，用于处理 SDK 返回的位姿格式。

        Args:
            position: LbotPosition 对象，包含 x, y, z（单位：米）
            euler: LbotEuler 对象，包含 x, y, z（对应 roll, pitch, yaw，单位：弧度）

        Returns:
            np.ndarray: 4x4 齐次变换矩阵

        Example:
            >>> pose = robot.get_cartesian_pose(LbotArm.LEFT_ARM)
            >>> if pose:
            >>>     position, euler = pose
            >>>     matrix = RobotInterface.lbot_pose_to_matrix(position, euler)
        """
        # 使用 scipy 将欧拉角（XYZ 顺序）转换为旋转矩阵
        rotation = R.from_euler('xyz', [euler.x, euler.y, euler.z], degrees=False)
        rotation_matrix = rotation.as_matrix()

        # 构建 4x4 齐次变换矩阵
        transform_matrix = np.eye(4)
        transform_matrix[:3, :3] = rotation_matrix
        transform_matrix[:3, 3] = [position.x, position.y, position.z]

        return transform_matrix


# ==================== Mock 实现示例 ====================

class MockRobotInterface(RobotInterface):
    """
    Mock 机械臂接口（用于测试）
    实际使用时，请根据你的机械臂 SDK 创建新的类
    """

    def __init__(self):
        # 模拟当前位姿（单位：米和弧度）
        self.current_x = 0.5
        self.current_y = 0.0
        self.current_z = 0.3
        self.current_rx = 0.0
        self.current_ry = 0.0
        self.current_rz = 0.0

    def get_current_pose(self) -> np.ndarray:
        """
        返回模拟的机械臂位姿
        """
        return self.pose_to_matrix(
            self.current_x, self.current_y, self.current_z,
            self.current_rx, self.current_ry, self.current_rz,
            rotation_type="euler_xyz"
        )

    def move_to(self, target_pose: np.ndarray) -> bool:
        """
        模拟移动（仅更新内部状态）
        """
        x, y, z, rx, ry, rz = self.matrix_to_pose(target_pose, rotation_type="euler_xyz")
        self.current_x = x
        self.current_y = y
        self.current_z = z
        self.current_rx = rx
        self.current_ry = ry
        self.current_rz = rz
        print(f"Mock Robot moved to: x={x:.3f}, y={y:.3f}, z={z:.3f}")
        return True


# ==================== LinkerArm (LBot) 机械臂接口实现 ====================

class LinkerArmInterface(RobotInterface):
    """
    LinkerArm (LBot) 机械臂接口实现

    使用 LBot SDK 控制 LinkerArm 双臂机器人
    """

    def __init__(self, tcp_host: str = "192.168.10.21", arm_side: str = "left", sdk_path: str = None,
                 move_speed: float = 0.3, move_accel: float = 0.1, move_block: bool = True):
        """
        初始化 LinkerArm 机械臂连接

        Args:
            tcp_host: 机器人控制器的 IP 地址
            arm_side: 使用的机械臂，"left" 或 "right"
            sdk_path: LBot SDK 的路径（可选）。如果不提供，将尝试自动查找。
                     例如: "/home/luka/.ssh/VIST/src/robot/sdk/linkerarm"
            move_speed: 运动速度 (m/s)
            move_accel: 加速度 (m/s²)
            move_block: 是否阻塞等待运动完成
        """
        import sys
        import os

        # 保存运动控制参数
        self.move_speed = move_speed
        self.move_accel = move_accel
        self.move_block = move_block

        # 确定 SDK 路径
        if sdk_path is None:
            # 尝试几个可能的路径
            possible_paths = [
                "/home/luka/.ssh/VIST/src/robot/sdk/linkerarm",
                os.path.join(os.path.dirname(__file__), "../VIST/src/robot/sdk/linkerarm"),
                os.path.join(os.path.dirname(__file__), "VIST/src/robot/sdk/linkerarm"),
            ]

            for path in possible_paths:
                abs_path = os.path.abspath(path)
                if os.path.exists(abs_path):
                    sdk_path = abs_path
                    break

            if sdk_path is None:
                raise ImportError(
                    f"无法找到 LBot SDK。请手动指定 sdk_path 参数。\n"
                    f"尝试的路径: {possible_paths}"
                )

        # 添加 SDK 路径到 Python 路径
        if sdk_path not in sys.path:
            sys.path.insert(0, sdk_path)

        try:
            from lbot.lbot_robot import LbotRobot
            from lbot.lbot_api import LbotArm
        except ImportError as e:
            raise ImportError(
                f"无法导入 LBot SDK。请确保 SDK 路径正确。\n"
                f"使用的路径: {sdk_path}\n"
                f"错误信息: {e}"
            )

        self.robot = LbotRobot(tcp_host)
        self.arm = LbotArm.LEFT_ARM if arm_side.lower() == "left" else LbotArm.RIGHT_ARM
        self.arm_name = arm_side.lower()

        # 连接到机器人
        print(f"正在连接到 LinkerArm 机器人 ({tcp_host})...")
        if not self.robot.connect():
            raise RuntimeError(f"无法连接到机器人: {self.robot.get_last_error()}")

        print(f"成功连接到 LinkerArm 机器人，使用 {arm_side} 臂")

    def get_current_pose(self) -> np.ndarray:
        """
        获取当前机械臂末端执行器的位姿

        Returns:
            np.ndarray: 4x4 齐次变换矩阵
        """
        pose = self.robot.get_cartesian_pose(self.arm)

        if pose is None:
            raise RuntimeError(
                f"无法获取机械臂位姿: {self.robot.get_last_error()}"
            )

        position, euler = pose

        # 使用 lbot_pose_to_matrix 辅助函数转换为 4x4 矩阵
        return self.lbot_pose_to_matrix(position, euler)

    def move_to(self, target_pose: np.ndarray) -> bool:
        """
        移动机械臂到指定位姿

        Args:
            target_pose: 4x4 齐次变换矩阵，目标位姿

        Returns:
            bool: 是否移动成功
        """
        try:
            from lbot.lbot_api import LbotPosition, LbotEuler
        except ImportError as e:
            print(f"无法导入 LBot API 类型: {e}")
            return False

        # 将 4x4 矩阵转换为位置和欧拉角
        x, y, z, rx, ry, rz = self.matrix_to_pose(
            target_pose,
            rotation_type="euler_xyz"
        )

        # 创建 LbotPosition 和 LbotEuler 对象
        position = LbotPosition(x, y, z)
        euler = LbotEuler(rx, ry, rz)

        # 调用机械臂运动控制（使用笛卡尔空间姿态运动）
        print(f"移动 {self.arm_name} 臂到目标位姿: pos=({x:.3f}, {y:.3f}, {z:.3f}), euler=({rx:.3f}, {ry:.3f}, {rz:.3f})")
        success = self.robot.move_to_pose_target(
            self.arm,
            position,
            euler,
            speed=self.move_speed,
            accel=self.move_accel,
            block=self.move_block
        )

        if not success:
            print(f"移动失败: {self.robot.get_last_error()}")
        else:
            print("移动成功")

        return success

    def disconnect(self):
        """
        断开机器人连接
        """
        if hasattr(self, 'robot'):
            self.robot.disconnect()
            print("已断开 LinkerArm 机器人连接")

    def __del__(self):
        """
        析构函数，确保断开连接
        """
        self.disconnect()


# ==================== 用户实现示例模板 ====================

class YourRobotInterface(RobotInterface):
    """
    用户自定义机械臂接口模板
    如果你使用的不是 LinkerArm，请根据你的机械臂 SDK 填写以下方法
    """

    def __init__(self):
        """
        初始化你的机械臂连接
        例如：
        - 导入你的机械臂 SDK
        - 建立连接
        - 初始化参数
        """
        # TODO: 在这里初始化你的机械臂
        # 例如：
        # from your_robot_sdk import RobotController
        # self.robot = RobotController()
        # self.robot.connect()
        pass

    def get_current_pose(self) -> np.ndarray:
        """
        实现：获取当前机械臂位姿
        """
        # TODO: 调用你的机械臂 SDK 获取当前位姿
        # 例如：
        # pose = self.robot.get_tcp_pose()  # 获取末端位姿

        # 情况1：如果返回的是 [x, y, z, rx, ry, rz] 格式
        # x, y, z, rx, ry, rz = pose
        # return self.pose_to_matrix(x, y, z, rx, ry, rz, rotation_type="euler_xyz")

        # 情况2：如果返回的是四元数 [x, y, z, qx, qy, qz, qw]
        # x, y, z, qx, qy, qz, qw = pose
        # return self.quaternion_to_matrix(x, y, z, qx, qy, qz, qw)

        # 情况3：如果返回的已经是 4x4 矩阵
        # return pose

        raise NotImplementedError("请实现 get_current_pose 方法")

    def move_to(self, target_pose: np.ndarray) -> bool:
        """
        实现：移动机械臂到指定位姿（可选）
        """
        # TODO: 调用你的机械臂 SDK 移动到目标位姿
        # 例如：
        # x, y, z, rx, ry, rz = self.matrix_to_pose(target_pose, rotation_type="euler_xyz")
        # success = self.robot.move_to(x, y, z, rx, ry, rz)
        # return success

        raise NotImplementedError("请实现 move_to 方法（可选）")


if __name__ == "__main__":
    # 测试 Mock 接口
    print("=" * 60)
    print("测试 Mock Robot Interface:")
    print("=" * 60)
    robot = MockRobotInterface()

    # 获取当前位姿
    pose = robot.get_current_pose()
    print(f"\n当前位姿矩阵:\n{pose}")

    # 测试坐标转换
    print("\n测试坐标转换:")
    x, y, z, rx, ry, rz = RobotInterface.matrix_to_pose(pose)
    print(f"位姿参数: x={x:.3f}, y={y:.3f}, z={z:.3f}, rx={rx:.3f}, ry={ry:.3f}, rz={rz:.3f}")

    # 测试四元数转换
    print("\n测试四元数转换:")
    matrix = RobotInterface.quaternion_to_matrix(0.5, 0.0, 0.3, 0, 0, 0, 1)
    print(f"四元数转矩阵:\n{matrix}")

    # 测试 LinkerArm 接口（如果可用）
    print("\n" + "=" * 60)
    print("测试 LinkerArm Interface:")
    print("=" * 60)
    print("如果要测试 LinkerArm 接口，请取消注释以下代码并确保机器人已连接：")
    print("""
    # 示例代码：
    try:
        # 创建 LinkerArm 接口（使用左臂）
        linker_robot = LinkerArmInterface(
            tcp_host="192.168.10.21",  # 修改为你的机器人 IP
            arm_side="left",            # 或 "right"
            sdk_path="/home/luka/.ssh/VIST/src/robot/sdk/linkerarm"  # 可选，自动查找
        )

        # 获取当前位姿
        current_pose = linker_robot.get_current_pose()
        print(f"当前位姿矩阵:\\n{current_pose}")

        # 移动到目标位姿（示例：在当前位置基础上沿 Z 轴移动 0.05 米）
        target_pose = current_pose.copy()
        target_pose[2, 3] += 0.05  # Z 轴移动 5cm
        success = linker_robot.move_to(target_pose)
        print(f"移动结果: {'成功' if success else '失败'}")

        # 断开连接
        linker_robot.disconnect()

    except Exception as e:
        print(f"LinkerArm 测试失败: {e}")
    """)