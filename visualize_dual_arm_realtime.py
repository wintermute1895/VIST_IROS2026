#!/usr/bin/env python3
"""
双臂机械臂Meshcat实时可视化
订阅左右臂ROS2话题，实时显示双臂状态

使用方法:
    python3 visualize_dual_arm_realtime.py

作者: VIST Team
日期: 2026-03-17
"""

import numpy as np
import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import re
from pathlib import Path
import sys

class DualArmMeshcatVisualizer(Node):
    def __init__(self, urdf_path):
        super().__init__('dual_arm_meshcat_visualizer')

        self.get_logger().info('=' * 60)
        self.get_logger().info('双臂机械臂Meshcat实时可视化')
        self.get_logger().info('=' * 60)

        # 准备URDF文件
        self.get_logger().info(f'加载URDF: {urdf_path.name}')
        meshcat_urdf = self.prepare_urdf_for_meshcat(urdf_path)

        # 加载机器人模型
        try:
            self.model, collision_model, visual_model = pin.buildModelsFromUrdf(str(meshcat_urdf))
            self.get_logger().info('✓ 加载完整模型（包括3D mesh）')
        except Exception as e:
            self.get_logger().warn(f'无法加载几何模型: {e}')
            self.get_logger().info('使用基础模型...')
            self.model = pin.buildModelFromUrdf(str(meshcat_urdf))
            collision_model = None
            visual_model = None

        self.data = self.model.createData()

        # 显示机器人信息
        self.get_logger().info(f'机器人信息:')
        self.get_logger().info(f'  关节总数: {self.model.nq}')
        self.get_logger().info(f'  自由度: {self.model.nv}')

        # 查找左右臂关节索引
        self.left_arm_indices = []
        self.right_arm_indices = []

        # 使用关节名称而不是frame名称
        left_joint_names = [
            'Left_Shoulder_Pitch_Joint',
            'Left_Shoulder_Roll_Joint',
            'Left_Shoulder_Yaw_Joint',
            'Left_Elbow_Pitch_Joint',
            'Left_Wrist_Yaw_Joint',
            'Left_Wrist_Pitch_Joint',
            'Left_Wrist_Roll_Joint'
        ]

        right_joint_names = [
            'Right_Shoulder_Pitch_Joint',
            'Right_Shoulder_Roll_Joint',
            'Right_Shoulder_Yaw_Joint',
            'Right_Elbow_Pitch_Joint',
            'Right_Wrist_Yaw_Joint',
            'Right_Wrist_Pitch_Joint',
            'Right_Wrist_Roll_Joint'
        ]

        # 查找关节在配置向量中的索引
        for joint_name in left_joint_names:
            try:
                joint_id = self.model.getJointId(joint_name)
                idx_q = self.model.joints[joint_id].idx_q
                self.left_arm_indices.append(idx_q)
            except Exception as e:
                self.get_logger().warn(f'未找到左臂关节: {joint_name}')

        for joint_name in right_joint_names:
            try:
                joint_id = self.model.getJointId(joint_name)
                idx_q = self.model.joints[joint_id].idx_q
                self.right_arm_indices.append(idx_q)
            except Exception as e:
                self.get_logger().warn(f'未找到右臂关节: {joint_name}')

        self.get_logger().info(f'左臂关节索引: {self.left_arm_indices}')
        self.get_logger().info(f'右臂关节索引: {self.right_arm_indices}')

        # 创建Meshcat可视化器
        self.get_logger().info('启动Meshcat可视化器...')
        self.viz = MeshcatVisualizer(self.model, collision_model, visual_model)

        try:
            self.viz.initViewer(open=True)  # 自动打开浏览器
            if visual_model is not None:
                self.viz.loadViewerModel()
            self.get_logger().info(f'✓ Meshcat已启动: {self.viz.viewer.url()}')
        except Exception as e:
            self.get_logger().error(f'无法启动Meshcat: {e}')
            sys.exit(1)

        # 初始化关节状态
        self.q = pin.neutral(self.model)

        # 显示初始状态
        pin.forwardKinematics(self.model, self.data, self.q)
        pin.updateFramePlacements(self.model, self.data)
        try:
            self.viz.display(self.q)
        except (AttributeError, Exception):
            pass

        # 订阅左臂关节状态话题
        self.left_subscription = self.create_subscription(
            JointState,
            '/filtered_left_joint_control',
            self.left_joint_callback,
            10
        )

        # 订阅右臂关节状态话题
        self.right_subscription = self.create_subscription(
            JointState,
            '/filtered_right_joint_control',
            self.right_joint_callback,
            10
        )

        self.get_logger().info('=' * 60)
        self.get_logger().info('等待双臂关节状态数据...')
        self.get_logger().info('订阅话题:')
        self.get_logger().info('  - /filtered_left_joint_control')
        self.get_logger().info('  - /filtered_right_joint_control')
        self.get_logger().info('=' * 60)

        # 统计
        self.left_update_count = 0
        self.right_update_count = 0
        self.last_log_time = self.get_clock().now()
        self.meshcat_urdf = meshcat_urdf

    def prepare_urdf_for_meshcat(self, original_urdf_path):
        """准备URDF文件用于Meshcat可视化"""
        with open(original_urdf_path, 'r') as f:
            content = f.read()

        # mesh文件的基础目录
        mesh_base_dir = original_urdf_path.parent.parent

        # 替换package://my_robot为绝对路径
        modified_content = re.sub(
            r'package://my_robot/',
            f'file://{mesh_base_dir}/',
            content
        )

        # 创建临时URDF文件
        temp_urdf = original_urdf_path.parent / f"{original_urdf_path.stem}_meshcat_dual_arm.urdf"
        with open(temp_urdf, 'w') as f:
            f.write(modified_content)

        return temp_urdf

    def left_joint_callback(self, msg):
        """接收左臂关节状态并更新可视化"""
        try:
            if len(msg.position) >= 7 and len(self.left_arm_indices) >= 7:
                # 接收的数据已经是正确方向，不需要再次修正
                joint_values = np.array(msg.position[0:7])

                # 单位转换（如果需要）
                if np.max(np.abs(joint_values)) > np.pi:
                    joint_values = np.deg2rad(joint_values)

                # 更新左臂关节
                for i, idx in enumerate(self.left_arm_indices[:7]):
                    if idx < self.model.nq:
                        self.q[idx] = joint_values[i]

                # 更新可视化
                self.update_visualization()
                self.left_update_count += 1

        except Exception as e:
            self.get_logger().error(f'左臂更新失败: {e}')

    def right_joint_callback(self, msg):
        """接收右臂关节状态并更新可视化"""
        try:
            if len(msg.position) >= 7 and len(self.right_arm_indices) >= 7:
                # 接收的数据已经是正确方向，不需要再次修正
                joint_values = np.array(msg.position[0:7])

                # 单位转换（如果需要）
                if np.max(np.abs(joint_values)) > np.pi:
                    joint_values = np.deg2rad(joint_values)

                # 更新右臂关节
                for i, idx in enumerate(self.right_arm_indices[:7]):
                    if idx < self.model.nq:
                        self.q[idx] = joint_values[i]

                # 更新可视化
                self.update_visualization()
                self.right_update_count += 1

        except Exception as e:
            self.get_logger().error(f'右臂更新失败: {e}')

    def update_visualization(self):
        """更新Meshcat可视化"""
        try:
            # 更新运动学
            pin.forwardKinematics(self.model, self.data, self.q)
            pin.updateFramePlacements(self.model, self.data)

            # 更新可视化
            self.viz.display(self.q)

            # 每秒打印一次统计
            current_time = self.get_clock().now()
            if (current_time - self.last_log_time).nanoseconds > 1e9:
                self.get_logger().info(
                    f'更新频率 - 左臂: {self.left_update_count} Hz | 右臂: {self.right_update_count} Hz'
                )
                self.left_update_count = 0
                self.right_update_count = 0
                self.last_log_time = current_time

        except Exception as e:
            self.get_logger().error(f'更新可视化失败: {e}')

    def cleanup(self):
        """清理临时文件"""
        if hasattr(self, 'meshcat_urdf') and self.meshcat_urdf.exists():
            self.meshcat_urdf.unlink()
            self.get_logger().info('✓ 清理临时文件')

def main(args=None):
    # URDF文件路径
    urdf_path = Path("/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description.urdf")

    if not urdf_path.exists():
        # 尝试备用路径
        urdf_path = Path("/home/ilex/Dev/VIST/config/lkls73_o2_dual_arm_description.urdf")
        if not urdf_path.exists():
            print(f"错误: URDF文件不存在")
            print(f"尝试的路径:")
            print(f"  - /home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description.urdf")
            print(f"  - /home/ilex/Dev/VIST/config/lkls73_o2_dual_arm_description.urdf")
            return

    rclpy.init(args=args)

    try:
        visualizer = DualArmMeshcatVisualizer(urdf_path)
        print(f"\n✓ 双臂可视化器已启动")
        print(f"  Meshcat URL: {visualizer.viz.viewer.url()}")
        print(f"  订阅话题:")
        print(f"    - /filtered_left_joint_control")
        print(f"    - /filtered_right_joint_control")
        print(f"\n在浏览器中查看双臂机械臂实时运动")
        print(f"按 Ctrl+C 停止\n")

        rclpy.spin(visualizer)

    except KeyboardInterrupt:
        print('\n\n双臂可视化器停止')
    finally:
        if 'visualizer' in locals():
            visualizer.cleanup()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()