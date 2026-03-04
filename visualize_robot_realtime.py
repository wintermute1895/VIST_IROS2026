#!/usr/bin/env python3
"""
机械臂Meshcat实时可视化
订阅ROS2话题，实时显示机械臂状态
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

class RobotMeshcatVisualizer(Node):
    def __init__(self, urdf_path):
        super().__init__('robot_meshcat_visualizer')

        self.get_logger().info('=' * 60)
        self.get_logger().info('机械臂Meshcat实时可视化')
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

        # 显示左臂关节
        self.get_logger().info(f'左臂关节:')
        for i in range(1, min(8, len(self.model.names))):
            self.get_logger().info(f'  {i}. {self.model.names[i]}')

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

        # 订阅关节状态话题
        self.subscription = self.create_subscription(
            JointState,
            '/filtered_left_joint_control',  # 订阅滤波后的关节控制话题
            self.joint_state_callback,
            10
        )

        self.get_logger().info('=' * 60)
        self.get_logger().info('等待关节状态数据...')
        self.get_logger().info('订阅话题: /filtered_left_joint_control')
        self.get_logger().info('=' * 60)

        # 统计
        self.update_count = 0
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
        temp_urdf = original_urdf_path.parent / f"{original_urdf_path.stem}_meshcat_realtime.urdf"
        with open(temp_urdf, 'w') as f:
            f.write(modified_content)

        return temp_urdf

    def joint_state_callback(self, msg):
        """接收关节状态并更新可视化"""
        try:
            # 提取关节位置
            if len(msg.position) >= 7:
                # 更新左臂关节（前7个）
                joint_values = np.array(msg.position[:7])

                # 对第2、3、4、5个关节（索引1、2、3、4）方向取反
                #joint_values[1] = -joint_values[1]
                joint_values[2] = -joint_values[2]
                joint_values[3] = -joint_values[3]
                joint_values[4] = -joint_values[4]

                # 统一转换为弧度（Pinocchio必须使用弧度）
                # 假设输入可能是角度，统一转换
                # 如果已经是弧度，转换后数值会很小但不影响正确性判断
                if np.max(np.abs(joint_values)) > np.pi:
                    # 数值超过π，确定是角度，转换为弧度
                    joint_values = np.deg2rad(joint_values)
                # 如果数值在合理的弧度范围内，直接使用



                # 更新关节状态
                for i in range(min(7, len(joint_values))):
                    if i < self.model.nq:
                        self.q[i] = joint_values[i]

                # 更新运动学
                pin.forwardKinematics(self.model, self.data, self.q)
                pin.updateFramePlacements(self.model, self.data)

                # 更新可视化
                try:
                    self.viz.display(self.q)
                except (AttributeError, Exception):
                    pass

                self.update_count += 1

                # 每秒打印一次统计
                current_time = self.get_clock().now()
                if (current_time - self.last_log_time).nanoseconds > 1e9:
                    self.get_logger().info(f'更新频率: {self.update_count} Hz | 关节角度: [{", ".join([f"{q:.2f}" for q in self.q[:7]])}]')
                    self.update_count = 0
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
        print(f"错误: URDF文件不存在: {urdf_path}")
        return

    rclpy.init(args=args)

    try:
        visualizer = RobotMeshcatVisualizer(urdf_path)
        print(f"\n✓ 可视化器已启动")
        print(f"  Meshcat URL: {visualizer.viz.viewer.url()}")
        print(f"  订阅话题: /filtered_left_joint_control")
        print(f"\n在浏览器中查看机械臂实时运动")
        print(f"按 Ctrl+C 停止\n")

        rclpy.spin(visualizer)

    except KeyboardInterrupt:
        print('\n\n可视化器停止')
    finally:
        if 'visualizer' in locals():
            visualizer.cleanup()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()
