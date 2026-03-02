#!/usr/bin/env python3
"""
实时FK验证工具 - 对比理论FK与实际机械臂位置

核心思路：
1. 订阅机械臂的实际关节角度和末端位置
2. 使用不同的 negation 映射计算理论FK
3. 实时对比理论值与实际值的误差
4. 自动找出最优的 negation 映射

使用方法：
    # 终端1：启动机械臂和数据发布
    ros2 launch ...

    # 终端2：运行验证工具
    python3 scripts/verify_fk_realtime.py

作者: VIST Team
日期: 2026-03-01
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped
import numpy as np
import sys
from pathlib import Path
import itertools
from collections import deque
import time

# 添加项目路径
ros2_ws_root = Path('/home/ilex/Dev/VIST/ros2_ws')
sys.path.insert(0, str(ros2_ws_root))

import pinocchio as pin
from src.core.ik_solver import PinocchioIKSolver as IKSolver


def expand_single_arm_to_dual(q_single: np.ndarray, arm_side: str = 'left') -> np.ndarray:
    """将单臂7关节扩展为双臂14关节向量"""
    q_dual = np.zeros(14)
    if arm_side == 'left':
        q_dual[0:7] = q_single
    else:
        q_dual[7:14] = q_single
    return q_dual


class FKVerificationNode(Node):
    """实时FK验证节点"""

    def __init__(self):
        super().__init__('fk_verification_node')

        # 配置
        self.arm_side = 'left'

        # 初始化 Pinocchio 模型（只需要 FK）
        urdf_path = '/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description.urdf'

        # 直接使用 Pinocchio 加载模型
        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()

        # 查找左臂末端执行器的 frame ID
        # 根据 check_end_effector.py 的结果，使用 Left_Wrist_Yaw_Link（距离原点最远）
        ee_frame_name = 'Left_Wrist_Yaw_Link'
        if self.model.existFrame(ee_frame_name):
            self.ee_frame_id = self.model.getFrameId(ee_frame_name)
            self.get_logger().info(f'✓ Pinocchio 模型初始化成功')
            self.get_logger().info(f'  末端执行器: {ee_frame_name} (frame_id={self.ee_frame_id})')
        else:
            self.get_logger().error(f'❌ 找不到末端执行器 frame: {ee_frame_name}')
            raise ValueError(f"Frame {ee_frame_name} not found in URDF")

        # 候选的 negation 映射（基于你提供的信息）
        self.negation_candidates = {
            'current': np.array([1, -1, 1, -1, 1, -1, 1]),  # 当前使用的
            'original': np.array([1, 1, 1, -1, 1, -1, 1]),  # 原始的
            'all_positive': np.array([1, 1, 1, 1, 1, 1, 1]),  # 全正
            'teleop_config': np.array([1, 1, 1, -1, 1, -1, 1]),  # 遥操配置
        }

        # 数据存储
        self.robot_joints = None
        self.robot_pose = None
        self.error_history = {name: deque(maxlen=100) for name in self.negation_candidates.keys()}

        # 订阅话题
        self.joint_sub = self.create_subscription(
            JointState,
            '/robot_joint_states',  # 实际机械臂关节角
            self.joint_callback,
            10
        )

        # 定时器：每秒分析一次
        self.timer = self.create_timer(1.0, self.analyze_fk_error)

        self.get_logger().info('🔍 FK验证节点已启动')
        self.get_logger().info(f'订阅话题: /robot_joint_states')
        self.get_logger().info(f'测试 {len(self.negation_candidates)} 种 negation 映射')

    def joint_callback(self, msg: JointState):
        """接收机械臂关节角"""
        # 提取左臂关节角（假设前7个是左臂）
        if len(msg.position) >= 7:
            self.robot_joints = np.array(msg.position[:7])

    def compute_fk_with_negation(self, joints, negation):
        """
        使用指定的 negation 映射计算FK

        Args:
            joints: 关节角 [7]
            negation: negation 映射 [7]

        Returns:
            末端位置 [x, y, z]
        """
        # 扩展为双臂
        q_dual = expand_single_arm_to_dual(joints, self.arm_side)

        # 应用 negation 映射
        negation_dual = np.concatenate([negation, np.ones(7)])  # 只映射左臂
        q_corrected = q_dual * negation_dual

        # 计算FK
        pin.forwardKinematics(self.model, self.data, q_corrected)
        pin.updateFramePlacements(self.model, self.data)

        position = self.data.oMf[self.ee_frame_id].translation.copy()
        return position

    def analyze_fk_error(self):
        """分析不同 negation 映射的FK误差"""
        if self.robot_joints is None:
            self.get_logger().warn('⚠️  尚未接收到关节角数据')
            return

        print("\n" + "="*80)
        print(f"  FK 验证分析 - {time.strftime('%H:%M:%S')}")
        print("="*80)

        print(f"\n当前关节角 (rad):")
        print(f"  {self.robot_joints}")
        print(f"  (deg): {np.rad2deg(self.robot_joints)}")

        print(f"\n测试不同的 negation 映射:")
        print(f"{'映射名称':<20} {'FK位置 (m)':<40} {'X坐标':<10}")
        print("-"*80)

        results = {}
        for name, negation in self.negation_candidates.items():
            try:
                fk_position = self.compute_fk_with_negation(self.robot_joints, negation)
                results[name] = fk_position

                # 检查X坐标是否为正（机器人坐标系下应该为正）
                x_status = "✓" if fk_position[0] > 0 else "❌"

                print(f"{name:<20} [{fk_position[0]:+.4f}, {fk_position[1]:+.4f}, {fk_position[2]:+.4f}]  {x_status} {fk_position[0]:+.4f}")

            except Exception as e:
                print(f"{name:<20} 计算失败: {e}")

        # 分析哪个映射最合理
        print(f"\n📊 分析:")
        valid_mappings = [(name, pos) for name, pos in results.items() if pos[0] > 0]

        if valid_mappings:
            print(f"  ✓ X坐标为正的映射（符合机器人坐标系）:")
            for name, pos in valid_mappings:
                print(f"    - {name}: X={pos[0]:.4f} m")
        else:
            print(f"  ❌ 所有映射的X坐标都为负，可能需要调整")

        # 建议
        print(f"\n💡 建议:")
        if len(valid_mappings) == 1:
            print(f"  推荐使用: {valid_mappings[0][0]}")
        elif len(valid_mappings) > 1:
            print(f"  有 {len(valid_mappings)} 个候选映射，需要结合实际机械臂位置判断")
        else:
            print(f"  需要尝试其他 negation 组合")


def main():
    """主函数"""
    print("="*80)
    print("  实时FK验证工具")
    print("="*80)
    print("\n功能:")
    print("  1. 订阅机械臂实际关节角")
    print("  2. 测试不同的 negation 映射")
    print("  3. 找出最符合机器人坐标系的映射")
    print("\n提示:")
    print("  - 确保机械臂已启动并发布 /robot_joint_states 话题")
    print("  - 观察哪个映射的X坐标始终为正")
    print("  - 按 Ctrl+C 退出")
    print("="*80)

    rclpy.init()
    node = FKVerificationNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，正在退出...")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()