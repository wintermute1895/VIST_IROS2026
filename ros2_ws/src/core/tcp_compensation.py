#!/usr/bin/env python3
"""
TCP 偏移补偿模块

处理末端执行器（灵巧手）的工具中心点（TCP）偏移。

功能：
1. TCP 位置偏移补偿
2. TCP 姿态偏移补偿
3. 多任务 TCP 配置
4. 标定和验证工具
"""

import numpy as np
from scipy.spatial.transform import Rotation
from typing import Tuple, Optional, Dict
import yaml
import os


class TCPCompensation:
    """
    TCP 偏移补偿

    将目标 TCP 位姿转换为法兰盘位姿，或反之。
    """

    def __init__(self, tcp_offset: np.ndarray = None, tcp_rotation: Rotation = None, task_name: str = 'default'):
        """
        初始化 TCP 补偿

        Args:
            tcp_offset: TCP 位置偏移 [x, y, z] (米)，相对于法兰盘
            tcp_rotation: TCP 姿态偏移（Rotation 对象）
            task_name: 任务名称（用于加载配置）
        """
        self.task_name = task_name

        # 如果未提供偏移，尝试从配置文件加载
        if tcp_offset is None or tcp_rotation is None:
            tcp_offset, tcp_rotation = self._load_from_config(task_name)

        self.tcp_offset = np.array(tcp_offset, dtype=np.float64)
        self.tcp_rotation = tcp_rotation

        print(f"🔧 [TCP] 初始化 TCP 补偿")
        print(f"   任务: {task_name}")
        print(f"   位置偏移: [{self.tcp_offset[0]:.3f}, {self.tcp_offset[1]:.3f}, {self.tcp_offset[2]:.3f}]m")
        print(f"   姿态偏移: {self.tcp_rotation.as_euler('xyz', degrees=True)} deg")

    def _load_from_config(self, task_name: str) -> Tuple[np.ndarray, Rotation]:
        """
        从配置文件加载 TCP 偏移

        Args:
            task_name: 任务名称

        Returns:
            tcp_offset: 位置偏移
            tcp_rotation: 姿态偏移
        """
        try:
            # 查找配置文件
            config_path = os.path.join(
                os.path.dirname(__file__), '..', '..', '..', 'config', 'tcp_calibration.yaml'
            )

            if not os.path.exists(config_path):
                print(f"⚠️ [TCP] 配置文件不存在: {config_path}")
                print(f"   使用默认值: [0, 0, 0.185]m")
                return np.array([0.0, 0.0, 0.185]), Rotation.identity()

            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            # 加载指定任务的 TCP 偏移
            tcp_config = config.get('tcp_offsets', {}).get(task_name, {})

            if not tcp_config:
                print(f"⚠️ [TCP] 任务 '{task_name}' 未找到，使用默认值")
                tcp_config = config.get('tcp_offsets', {}).get('default', {})

            position = np.array(tcp_config.get('position', [0.0, 0.0, 0.185]))
            orientation_quat = tcp_config.get('orientation', [0.0, 0.0, 0.0, 1.0])
            orientation = Rotation.from_quat(orientation_quat)

            return position, orientation

        except Exception as e:
            print(f"⚠️ [TCP] 加载配置失败: {e}")
            print(f"   使用默认值: [0, 0, 0.185]m")
            return np.array([0.0, 0.0, 0.185]), Rotation.identity()

    def compensate_target_pose(
        self,
        target_pos: np.ndarray,
        target_quat: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        补偿目标位姿（TCP → 法兰盘）

        将目标 TCP 位姿转换为法兰盘位姿。

        Args:
            target_pos: 目标 TCP 位置 [x, y, z] (米)
            target_quat: 目标 TCP 姿态（四元数 [x, y, z, w]，可选）

        Returns:
            flange_pos: 法兰盘位置
            flange_quat: 法兰盘姿态（如果提供了 target_quat）
        """
        # 1. 位置补偿
        if target_quat is not None:
            # 考虑姿态的影响
            R_target = Rotation.from_quat(target_quat)
            # TCP 偏移在法兰盘坐标系中，需要转换到世界坐标系
            offset_world = R_target.apply(self.tcp_offset)
            flange_pos = target_pos - offset_world
        else:
            # 简化：假设姿态为零（TCP 偏移沿 Z 轴）
            flange_pos = target_pos - self.tcp_offset

        # 2. 姿态补偿
        if target_quat is not None:
            R_target = Rotation.from_quat(target_quat)
            # 法兰盘姿态 = TCP 姿态 * TCP 姿态偏移的逆
            R_flange = R_target * self.tcp_rotation.inv()
            flange_quat = R_flange.as_quat()
        else:
            flange_quat = None

        return flange_pos, flange_quat

    def compensate_current_pose(
        self,
        flange_pos: np.ndarray,
        flange_quat: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        补偿当前位姿（法兰盘 → TCP）

        将法兰盘位姿转换为 TCP 位姿。

        Args:
            flange_pos: 法兰盘位置 [x, y, z] (米)
            flange_quat: 法兰盘姿态（四元数 [x, y, z, w]，可选）

        Returns:
            tcp_pos: TCP 位置
            tcp_quat: TCP 姿态（如果提供了 flange_quat）
        """
        # 1. 位置补偿
        if flange_quat is not None:
            R_flange = Rotation.from_quat(flange_quat)
            # TCP 偏移在法兰盘坐标系中，需要转换到世界坐标系
            offset_world = R_flange.apply(self.tcp_offset)
            tcp_pos = flange_pos + offset_world
        else:
            # 简化：假设姿态为零
            tcp_pos = flange_pos + self.tcp_offset

        # 2. 姿态补偿
        if flange_quat is not None:
            R_flange = Rotation.from_quat(flange_quat)
            # TCP 姿态 = 法兰盘姿态 * TCP 姿态偏移
            R_tcp = R_flange * self.tcp_rotation
            tcp_quat = R_tcp.as_quat()
        else:
            tcp_quat = None

        return tcp_pos, tcp_quat

    def get_offset_magnitude(self) -> float:
        """获取 TCP 偏移的大小（米）"""
        return np.linalg.norm(self.tcp_offset)

    def __str__(self) -> str:
        return (
            f"TCPCompensation(task={self.task_name}, "
            f"offset={self.tcp_offset}, "
            f"magnitude={self.get_offset_magnitude():.3f}m)"
        )


# ==========================================
# 标定工具
# ==========================================

def calibrate_tcp_by_teaching(robot, num_points: int = 4) -> np.ndarray:
    """
    通过示教标定 TCP 偏移

    Args:
        robot: 机器人接口
        num_points: 示教点数量（至少 4 个）

    Returns:
        tcp_offset: 标定得到的 TCP 偏移 [x, y, z]
    """
    from scipy.optimize import least_squares

    print(f"🎯 [TCP] 开始示教标定（需要 {num_points} 个点）")
    print("   请准备一个标定块，并标记其 4 个角的位置")

    # 1. 示教点
    taught_points = []
    for i in range(num_points):
        input(f"\n移动机器人末端到第 {i+1} 个点，按回车继续...")

        # 记录当前关节角度
        joint_angles = robot.get_joint_angles()

        # 计算法兰盘位置（正运动学）
        flange_pos = robot.forward_kinematics(joint_angles)

        taught_points.append(flange_pos)
        print(f"   记录点 {i+1}: {flange_pos}")

    # 2. 输入已知位置
    print("\n请输入标定块 4 个角的已知位置（世界坐标系）:")
    known_points = []
    for i in range(num_points):
        x = float(input(f"点 {i+1} - X (米): "))
        y = float(input(f"点 {i+1} - Y (米): "))
        z = float(input(f"点 {i+1} - Z (米): "))
        known_points.append([x, y, z])

    known_points = np.array(known_points)

    # 3. 优化求解 TCP 偏移
    def residual(tcp_offset):
        """残差函数"""
        errors = []
        for flange_pos, known_pos in zip(taught_points, known_points):
            # 假设 TCP = 法兰盘位置 + 偏移（简化，不考虑姿态）
            tcp_pos = flange_pos + tcp_offset
            error = tcp_pos - known_pos
            errors.extend(error)
        return errors

    # 初始猜测：[0, 0, 150mm]
    x0 = np.array([0.0, 0.0, 0.15])

    # 最小二乘优化
    result = least_squares(residual, x0)
    tcp_offset = result.x

    # 计算残差
    residuals = residual(tcp_offset)
    rms_error = np.sqrt(np.mean(np.array(residuals)**2))

    print(f"\n✅ [TCP] 标定完成")
    print(f"   TCP 偏移: [{tcp_offset[0]:.4f}, {tcp_offset[1]:.4f}, {tcp_offset[2]:.4f}]m")
    print(f"   RMS 误差: {rms_error*1000:.2f}mm")

    return tcp_offset


def verify_tcp_calibration(robot, tcp_compensation: TCPCompensation, test_positions: list) -> Dict:
    """
    验证 TCP 标定精度

    Args:
        robot: 机器人接口
        tcp_compensation: TCP 补偿对象
        test_positions: 测试位置列表（世界坐标系）

    Returns:
        统计信息字典
    """
    print(f"🔍 [TCP] 开始验证标定精度（{len(test_positions)} 个测试点）")

    errors = []
    for i, target_pos in enumerate(test_positions):
        # 1. 补偿目标位置（TCP → 法兰盘）
        flange_pos, _ = tcp_compensation.compensate_target_pose(target_pos)

        # 2. 移动到目标位置
        robot.move_to_position(flange_pos)

        # 3. 测量实际位置（需要外部测量系统，如视觉）
        print(f"\n测试点 {i+1}: 目标 TCP 位置 = {target_pos}")
        actual_pos_str = input("   请输入实际 TCP 位置 [x, y, z]（用空格分隔）: ")
        actual_pos = np.array([float(x) for x in actual_pos_str.split()])

        # 4. 计算误差
        error = np.linalg.norm(actual_pos - target_pos)
        errors.append(error)

        print(f"   误差: {error*1000:.2f}mm")

    # 统计
    errors = np.array(errors)
    stats = {
        'mean_error': np.mean(errors),
        'max_error': np.max(errors),
        'std_error': np.std(errors),
        'errors': errors
    }

    print(f"\n📊 [TCP] 验证结果:")
    print(f"   平均误差: {stats['mean_error']*1000:.2f}mm")
    print(f"   最大误差: {stats['max_error']*1000:.2f}mm")
    print(f"   标准差: {stats['std_error']*1000:.2f}mm")

    return stats


# ==========================================
# 示例使用
# ==========================================

if __name__ == "__main__":
    # 示例 1: 使用默认 TCP 偏移
    tcp_comp = TCPCompensation()

    # 示例 2: 手动指定 TCP 偏移
    tcp_comp = TCPCompensation(
        tcp_offset=[0.0, 0.0, 0.185],  # 185mm
        tcp_rotation=Rotation.identity()
    )

    # 示例 3: 加载特定任务的 TCP 偏移
    tcp_comp = TCPCompensation(task_name='usb_insertion')

    # 示例 4: 补偿目标位姿
    target_tcp_pos = np.array([0.5, 0.0, 0.3])
    flange_pos, _ = tcp_comp.compensate_target_pose(target_tcp_pos)
    print(f"目标 TCP 位置: {target_tcp_pos}")
    print(f"法兰盘位置: {flange_pos}")
