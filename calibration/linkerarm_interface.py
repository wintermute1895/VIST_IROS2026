"""
LinkerArm 机器人接口实现
========================
用于连接 LinkerArm (LBot) 双臂机器人进行手眼标定数据采集。
"""

import sys
from pathlib import Path
import numpy as np
from robot_interface import RobotInterface, process_raw_pose
import config


class LinkerArmInterface(RobotInterface):
    """
    LinkerArm (LBot) 机器人接口实现

    使用 LBot SDK 控制 LinkerArm 双臂机器人
    """

    def __init__(
        self,
        tcp_host: str = "192.168.10.21",
        arm_side: str = "left",
        sdk_path: str = None
    ):
        """
        初始化 LinkerArm 机器人连接

        Args:
            tcp_host: 机器人控制器的 IP 地址
            arm_side: 使用的机械臂，"left" 或 "right"
            sdk_path: LBot SDK 的路径（可选）
        """
        # 确定 SDK 路径
        if sdk_path is None:
            # 计算相对于当前文件的 SDK 路径
            project_root = Path(__file__).parent.parent
            sdk_path = project_root / "src" / "robot" / "sdk" / "linkerarm"

            if not sdk_path.exists():
                raise ImportError(
                    f"无法找到 LBot SDK: {sdk_path}\n"
                    f"请确保 SDK 已安装在正确的位置，或手动指定 sdk_path 参数"
                )

        # 添加 SDK 路径到 Python 路径
        sdk_path_str = str(sdk_path)
        if sdk_path_str not in sys.path:
            sys.path.insert(0, sdk_path_str)

        # 导入 LBot SDK
        try:
            from lbot.lbot_api import LbotAPI, LbotArm
            self.LbotAPI = LbotAPI
            self.LbotArm = LbotArm
        except ImportError as e:
            raise ImportError(
                f"无法导入 LBot SDK: {e}\n"
                f"SDK 路径: {sdk_path_str}\n"
                f"请确保 SDK 已正确安装"
            )

        # 连接到机器人
        self.tcp_host = tcp_host
        self.arm_side = arm_side.lower()

        # 创建 API 实例
        self.api = self.LbotAPI()

        # 初始化连接
        print(f"正在连接到 LinkerArm @ {tcp_host}...")
        if not self.api.init(tcp_host):
            raise RuntimeError(f"无法连接到机器人: {tcp_host}")

        # 启动状态监控
        print("正在启动状态监控...")
        if not self.api.start_state_monitor():
            raise RuntimeError("无法启动状态监控")

        # 等待状态更新
        import time
        time.sleep(0.5)  # 等待状态监控启动

        # 选择机械臂
        if self.arm_side == "left":
            self.arm = self.LbotArm.LEFT_ARM
        elif self.arm_side == "right":
            self.arm = self.LbotArm.RIGHT_ARM
        else:
            raise ValueError(f"无效的机械臂选择: {arm_side}，必须是 'left' 或 'right'")

        print(f"✓ 已连接到 LinkerArm ({arm_side} arm) @ {tcp_host}")

    def get_pose(self) -> np.ndarray:
        """
        获取当前机器人末端执行器相对于基座的位姿

        Returns:
            np.ndarray: 4x4 齐次变换矩阵 T_base_to_flange
        """
        # 从 LBot SDK 获取当前状态
        state = self.api.get_current_state()

        if state is None:
            raise RuntimeError("无法获取机器人状态")

        # 根据选择的机械臂获取对应的状态
        if self.arm_side == "left":
            arm_state = state.left_arm
        else:
            arm_state = state.right_arm

        # 提取位置和欧拉角
        position = arm_state.end_effector_position
        euler = arm_state.euler

        # 构建位姿数组: [x, y, z, rx, ry, rz]
        # LBot 返回格式: 米，弧度，欧拉角 XYZ 内旋
        raw_pose = [
            position.x,
            position.y,
            position.z,
            euler.x,  # roll
            euler.y,  # pitch
            euler.z   # yaw
        ]

        # 使用通用转换器转换为 4x4 矩阵
        T_base_to_flange = process_raw_pose(raw_pose, config.ROBOT_POSE_FMT)

        return T_base_to_flange

    def disconnect(self):
        """断开与机器人的连接"""
        try:
            self.api.stop_state_monitor()
            self.api.cleanup()
            print("✓ 已断开与机器人的连接")
        except Exception as e:
            print(f"断开连接时出错: {e}")


def test_connection():
    """测试 LinkerArm 连接"""
    print("\n" + "="*70)
    print("测试 LinkerArm 连接")
    print("="*70 + "\n")

    try:
        # 创建机器人接口
        # 请根据实际情况修改 IP 地址和机械臂选择
        robot = LinkerArmInterface(
            tcp_host="192.168.10.21",  # 修改为你的机器人 IP
            arm_side="right"             # 或 "right"
        )

        # 获取当前位姿
        pose = robot.get_pose()

        print("当前位姿矩阵 (4x4):")
        print(pose)
        print()

        print("位置 (米):")
        print(f"  x = {pose[0, 3]:.4f}")
        print(f"  y = {pose[1, 3]:.4f}")
        print(f"  z = {pose[2, 3]:.4f}")
        print()

        print("✓ 连接测试成功\n")

        return robot

    except Exception as e:
        print(f"✗ 连接测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    # 运行连接测试
    robot = test_connection()

    if robot:
        robot.disconnect()
