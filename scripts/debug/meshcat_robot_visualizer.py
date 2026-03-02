#!/usr/bin/env python3
"""
MeshCat 机器人实时可视化节点

功能：
1. 订阅 robot1/left_arm/joint_states 话题
2. 加载 URDF 模型
3. 在 MeshCat 中实时显示机器人状态
4. 帮助诊断 URDF 关节方向定义与电机控制的不匹配

使用方法：
    python3 scripts/debug/meshcat_robot_visualizer.py

作者: VIST Team
日期: 2026-03-02
"""

import os
import sys
import time
import numpy as np
import pinocchio as pin
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

# ROS2 导入
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class MeshCatRobotVisualizer(Node):
    """MeshCat 机器人可视化节点"""

    def __init__(self):
        super().__init__('meshcat_robot_visualizer')

        print("=" * 80)
        print("🎨 MeshCat 机器人实时可视化")
        print("=" * 80)

        # 1. 加载 URDF 模型
        print("\n📁 加载 URDF 模型...")
        urdf_path = '/home/ilex/Dev/VIST/ros2_ws/src/vist_description/urdf/lkls73_o2_dual_arm_description.urdf'

        if not os.path.exists(urdf_path):
            self.get_logger().error(f"❌ URDF 文件不存在: {urdf_path}")
            raise FileNotFoundError(f"URDF file not found: {urdf_path}")

        # 创建临时 URDF 文件，替换 package:// 路径
        import tempfile
        with open(urdf_path, 'r') as f:
            urdf_content = f.read()

        # 替换 package://my_robot/ 为实际路径
        mesh_dir = '/home/ilex/Dev/VIST/config/'
        urdf_content = urdf_content.replace('package://my_robot/', mesh_dir)

        # 写入临时文件
        temp_urdf = tempfile.NamedTemporaryFile(mode='w', suffix='.urdf', delete=False)
        temp_urdf.write(urdf_content)
        temp_urdf.close()
        self.temp_urdf_path = temp_urdf.name

        print(f"   原始 URDF: {urdf_path}")
        print(f"   临时 URDF: {self.temp_urdf_path}")
        print(f"   Mesh 目录: {mesh_dir}")

        # 加载 Pinocchio 模型（使用临时文件）
        self.model = pin.buildModelFromUrdf(self.temp_urdf_path)
        self.data = self.model.createData()

        # 加载可视化模型
        self.collision_model = pin.buildGeomFromUrdf(
            self.model, self.temp_urdf_path, pin.GeometryType.COLLISION
        )
        self.visual_model = pin.buildGeomFromUrdf(
            self.model, self.temp_urdf_path, pin.GeometryType.VISUAL
        )

        print(f"✅ URDF 加载成功")
        print(f"   关节数量: {self.model.nq}")
        print(f"   速度维度: {self.model.nv}")
        print(f"   视觉对象: {len(self.visual_model.geometryObjects)}")

        # 2. 初始化 MeshCat
        print("\n🎨 初始化 MeshCat 可视化...")
        self.vis = meshcat.Visualizer()
        print(f"✅ MeshCat 服务器启动")
        print(f"   URL: {self.vis.url()}")
        print(f"   请在浏览器中打开: {self.vis.url()}")

        # 3. 初始化 Pinocchio MeshCat 可视化器
        from pinocchio.visualize import MeshcatVisualizer
        self.robot_viz = MeshcatVisualizer(
            self.model,
            self.collision_model,
            self.visual_model
        )
        self.robot_viz.initViewer(viewer=self.vis)
        self.robot_viz.loadViewerModel(rootNodeName="robot")
        print("✅ 机器人模型加载完成")

        # 4. 设置场景
        self._setup_scene()

        # 5. 初始化关节状态
        self.q_current = pin.neutral(self.model).copy()
        self.last_update_time = time.time()
        self.frame_count = 0

        # 6. 创建 ROS2 订阅器
        print("\n📡 创建 ROS2 订阅器...")
        self.joint_state_sub = self.create_subscription(
            JointState,
            'robot1/left_arm/joint_states',
            self.joint_state_callback,
            10
        )
        print("✅ 订阅话题: robot1/left_arm/joint_states")

        # 7. 创建定时器（用于打印统计信息）
        self.stats_timer = self.create_timer(1.0, self.print_stats)

        # 8. 关节名称映射（URDF 中的关节名称 - 左臂7个）
        self.left_joint_names = [
            'Left_Shoulder_Pitch_Joint',
            'Left_Shoulder_Roll_Joint',
            'Left_Shoulder_Yaw_Joint',
            'Left_Elbow_Pitch_Joint',
            'Left_Wrist_Yaw_Joint',
            'Left_Wrist_Pitch_Joint',
            'Left_Wrist_Roll_Joint'
        ]

        # 右臂关节名称（固定为0）
        self.right_joint_names = [
            'Right_Shoulder_Pitch_Joint',
            'Right_Shoulder_Roll_Joint',
            'Right_Shoulder_Yaw_Joint',
            'Right_Elbow_Pitch_Joint',
            'Right_Wrist_Yaw_Joint',
            'Right_Wrist_Pitch_Joint',
            'Right_Wrist_Roll_Joint'
        ]

        # 9. 关节索引映射（URDF 中的关节索引）
        print("\n📋 左臂关节映射:")
        self.left_joint_indices = []
        for name in self.left_joint_names:
            if self.model.existJointName(name):
                joint_id = self.model.getJointId(name)
                idx_q = self.model.joints[joint_id].idx_q
                self.left_joint_indices.append(idx_q)
                print(f"   ✓ {name}: joint_id={joint_id}, idx_q={idx_q}")
            else:
                self.get_logger().error(f"   ❌ 找不到关节: {name}")
                self.left_joint_indices.append(-1)

        print("\n📋 右臂关节映射（固定为0）:")
        self.right_joint_indices = []
        for name in self.right_joint_names:
            if self.model.existJointName(name):
                joint_id = self.model.getJointId(name)
                idx_q = self.model.joints[joint_id].idx_q
                self.right_joint_indices.append(idx_q)
                # 将右臂关节固定为0
                self.q_current[idx_q] = 0.0
                print(f"   ✓ {name}: joint_id={joint_id}, idx_q={idx_q} (固定为0)")
            else:
                self.get_logger().error(f"   ❌ 找不到关节: {name}")
                self.right_joint_indices.append(-1)

        print("\n✅ 初始化完成！")
        print("\n" + "=" * 80)
        print("📊 实时可视化已启动")
        print("   - 移动机器人，观察 MeshCat 中的变化")
        print("   - 检查关节运动方向是否与预期一致")
        print("   - 按 Ctrl+C 停止")
        print("=" * 80 + "\n")

    def _setup_scene(self):
        """设置可视化场景"""
        print("\n🎨 设置可视化场景...")

        # 不要清空整个场景！机器人模型已经加载了
        # self.vis.delete()  # ❌ 这会删除机器人模型

        # 添加坐标系（机器人基座）
        axis_length = 0.3

        # X轴 - 红色（向前）
        x_axis_points = np.array([[0, 0, 0], [axis_length, 0, 0]]).T
        self.vis["robot_frame"]["x_axis"].set_object(
            g.Line(g.PointsGeometry(x_axis_points),
                   g.MeshBasicMaterial(color=0xff0000, linewidth=5))
        )

        # Y轴 - 绿色（向左）
        y_axis_points = np.array([[0, 0, 0], [0, axis_length, 0]]).T
        self.vis["robot_frame"]["y_axis"].set_object(
            g.Line(g.PointsGeometry(y_axis_points),
                   g.MeshBasicMaterial(color=0x00ff00, linewidth=5))
        )

        # Z轴 - 蓝色（向上）
        z_axis_points = np.array([[0, 0, 0], [0, 0, axis_length]]).T
        self.vis["robot_frame"]["z_axis"].set_object(
            g.Line(g.PointsGeometry(z_axis_points),
                   g.MeshBasicMaterial(color=0x0000ff, linewidth=5))
        )

        # 添加网格地面
        self.vis["ground"].set_object(
            g.Box([2.0, 2.0, 0.01]),
            g.MeshLambertMaterial(color=0x808080, opacity=0.3)
        )
        self.vis["ground"].set_transform(
            tf.translation_matrix([0, 0, -0.005])
        )

        print("✅ 场景设置完成")

    def joint_state_callback(self, msg: JointState):
        """
        关节状态回调函数

        Args:
            msg: JointState 消息（只包含左臂7个关节）
        """
        try:
            # 检查消息是否包含位置数据
            if not msg.position or len(msg.position) == 0:
                return

            # 更新左臂关节角度（只更新左臂，右臂保持为0）
            # 假设消息中的关节顺序与 self.left_joint_names 一致
            for i, idx_q in enumerate(self.left_joint_indices):
                if idx_q >= 0 and i < len(msg.position):
                    # 🔧 关键修正：第3、4、6个关节（索引2、3、5）需要反向
                    # 因为 URDF 定义的方向与电机控制方向不一致
                    if i == 2 or i == 3 or i == 5:  # 第3个（Shoulder_Yaw）、第4个（Elbow_Pitch）、第6个（Wrist_Pitch）
                        self.q_current[idx_q] = -msg.position[i]  # 取反
                    else:
                        self.q_current[idx_q] = msg.position[i]

            # 确保右臂关节保持为0（防止意外修改）
            for idx_q in self.right_joint_indices:
                if idx_q >= 0:
                    self.q_current[idx_q] = 0.0

            # 更新可视化（MeshCat 会根据 FK 计算显示末端位置）
            self.robot_viz.display(self.q_current)

            # 更新统计信息
            self.frame_count += 1
            self.last_update_time = time.time()

        except Exception as e:
            self.get_logger().error(f"❌ 更新可视化时出错: {e}")
            import traceback
            traceback.print_exc()

    def print_stats(self):
        """打印统计信息"""
        if self.frame_count > 0:
            elapsed = time.time() - self.last_update_time
            if elapsed < 2.0:  # 只在最近2秒内有数据时打印
                self.get_logger().info(
                    f"📊 已接收 {self.frame_count} 帧 | "
                    f"最后更新: {elapsed:.2f}秒前"
                )

    def cleanup(self):
        """清理临时文件"""
        if hasattr(self, 'temp_urdf_path') and os.path.exists(self.temp_urdf_path):
            try:
                os.remove(self.temp_urdf_path)
                print(f"🗑️  已清理临时文件: {self.temp_urdf_path}")
            except Exception as e:
                print(f"⚠️  清理临时文件失败: {e}")

    def get_joint_info(self):
        """
        获取关节信息（用于调试）

        Returns:
            dict: 关节信息字典
        """
        info = {}
        for i, name in enumerate(self.joint_names):
            if self.model.existJointName(name):
                joint_id = self.model.getJointId(name)
                idx_q = self.model.joints[joint_id].idx_q
                idx_v = self.model.joints[joint_id].idx_v

                info[name] = {
                    'joint_id': joint_id,
                    'idx_q': idx_q,
                    'idx_v': idx_v,
                    'current_value': self.q_current[idx_q] if idx_q < len(self.q_current) else None
                }

        return info


def main(args=None):
    """主函数"""
    rclpy.init(args=args)

    try:
        visualizer = MeshCatRobotVisualizer()

        print("\n🚀 开始接收关节状态数据...")
        print("   提示：")
        print("   1. 确保机器人驱动节点正在运行")
        print("   2. 确保发布 rot1/left_arm/joint_states 话题")
        print("   3. 移动机器人，观察 MeshCat 中的变化")
        print("   4. 检查每个关节的运动方向是否正确")
        print()

        rclpy.spin(visualizer)

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'visualizer' in locals():
            visualizer.cleanup()  # 清理临时文件
            visualizer.destroy_node()
        rclpy.shutdown()
        print("\n✅ 可视化节点已退出")


if __name__ == '__main__':
    main()