#!/usr/bin/env python3
"""
在仿真环境中回放录制的视觉数据

功能：
1. 读取rosbag中的关节角度数据
2. 使用MeshCat进行3D可视化
3. 按照录制的时间戳回放机器人运动
4. 显示性能指标（速度、加速度等）

使用方法：
    python3 scripts/replay_in_simulation.py data/vision_recordings/rec_YYYYMMDD_HHMMSS/rosbag
"""

import os
import sys
import time
import numpy as np
import argparse
from pathlib import Path

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    import meshcat
    import meshcat.geometry as g
    import meshcat.transformations as tf
except ImportError:
    print("❌ 错误: 未安装meshcat")
    print("请运行: pip install meshcat")
    sys.exit(1)

try:
    import pinocchio as pin
except ImportError:
    print("❌ 错误: 未安装pinocchio")
    print("请运行: pip install pin")
    sys.exit(1)

try:
    from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import JointState
except ImportError:
    print("❌ 错误: 未安装ROS2 Python库")
    print("请确保已source ROS2环境")
    sys.exit(1)

from src.config import get_config
from src.core.ik_solver import PinocchioIKSolver


class SimulationReplayer:
    """仿真回放器：读取rosbag并在MeshCat中可视化"""

    def __init__(self, bag_path: str, playback_speed: float = 1.0):
        """
        初始化回放器

        Args:
            bag_path: rosbag路径
            playback_speed: 回放速度倍率（1.0=原速，2.0=2倍速）
        """
        self.bag_path = bag_path
        self.playback_speed = playback_speed

        print("=" * 80)
        print("🎬 VIST 仿真回放器")
        print("=" * 80)
        print(f"📁 数据路径: {bag_path}")
        print(f"⚡ 回放速度: {playback_speed}x")
        print()

        # 1. 加载配置
        print("📋 加载配置...")
        self.config = get_config()

        # 2. 初始化IK求解器（用于正运动学）
        print("🧠 初始化IK求解器...")
        # 从配置中获取URDF路径
        urdf_file = getattr(self.config, 'urdf_file', 'urdf/lkls73_o2_dual_arm_description.urdf')
        if not os.path.isabs(urdf_file):
            # 如果是相对路径，转换为绝对路径
            urdf_path = os.path.join(project_root, 'config', urdf_file)
        else:
            urdf_path = urdf_file
        self.ik_solver = PinocchioIKSolver(urdf_path=urdf_path)

        # 3. 初始化MeshCat可视化
        print("🎨 启动MeshCat可视化...")
        self.vis = meshcat.Visualizer()
        print(f"✅ MeshCat已启动: {self.vis.url()}")

        # 4. 加载机器人模型到可视化器
        self._setup_visualization()

        # 5. 读取rosbag数据
        print("📦 读取rosbag数据...")
        self.messages = self._read_rosbag()
        print(f"✅ 读取到 {len(self.messages)} 条消息")
        print()

    def _setup_visualization(self):
        """设置可视化环境"""
        # 清空场景
        self.vis.delete()

        # 添加坐标系
        self.vis["/world"].set_transform(tf.translation_matrix([0, 0, 0]))

        # 添加地面网格
        grid_size = 2.0
        grid_divisions = 20
        self.vis["/grid"].set_object(
            g.LineSegments(
                g.PointsGeometry(
                    position=self._create_grid(grid_size, grid_divisions),
                    color=np.array([[0.5, 0.5, 0.5]] * (grid_divisions * 4 + 4)).T
                ),
                g.LineBasicMaterial(vertexColors=True)
            )
        )

        # 加载机器人URDF到可视化器
        try:
            # 使用Pinocchio的可视化功能
            from pinocchio.visualize import MeshcatVisualizer
            self.robot_viz = MeshcatVisualizer(
                self.ik_solver.model,
                self.ik_solver.collision_model,
                self.ik_solver.visual_model
            )
            self.robot_viz.initViewer(viewer=self.vis)
            self.robot_viz.loadViewerModel(rootNodeName="robot")
            print("✅ 机器人模型加载成功")
        except Exception as e:
            print(f"⚠️  警告: 无法加载机器人可视化模型: {e}")
            self.robot_viz = None

    def _create_grid(self, size: float, divisions: int) -> np.ndarray:
        """创建地面网格"""
        points = []
        step = size / divisions
        for i in range(divisions + 1):
            # X方向线
            points.append([-size/2 + i*step, -size/2, 0])
            points.append([-size/2 + i*step, size/2, 0])
            # Y方向线
            points.append([-size/2, -size/2 + i*step, 0])
            points.append([size/2, -size/2 + i*step, 0])
        return np.array(points).T

    def _read_rosbag(self) -> list:
        """读取rosbag中的所有消息"""
        messages = []

        # 配置rosbag读取器
        storage_options = StorageOptions(uri=self.bag_path, storage_id='sqlite3')
        converter_options = ConverterOptions(
            input_serialization_format='cdr',
            output_serialization_format='cdr'
        )

        reader = SequentialReader()
        reader.open(storage_options, converter_options)

        # 读取所有消息
        while reader.has_next():
            topic, data, timestamp = reader.read_next()

            # 反序列化消息
            msg = deserialize_message(data, JointState)

            messages.append({
                'timestamp': timestamp,
                'topic': topic,
                'msg': msg
            })

        return messages

    def replay(self):
        """回放数据"""
        if not self.messages:
            print("❌ 没有数据可回放")
            return

        print("=" * 80)
        print("▶️  开始回放")
        print("=" * 80)
        print("提示:")
        print("  - 在浏览器中打开MeshCat查看可视化")
        print("  - 按 Ctrl+C 停止回放")
        print()

        # 获取起始时间
        start_timestamp = self.messages[0]['timestamp']
        start_time = time.time()

        try:
            for i, msg_data in enumerate(self.messages):
                # 计算应该等待的时间
                msg_timestamp = msg_data['timestamp']
                elapsed_sim = (msg_timestamp - start_timestamp) / 1e9  # 纳秒转秒
                elapsed_real = time.time() - start_time

                # 根据回放速度调整等待时间
                target_time = elapsed_sim / self.playback_speed
                wait_time = target_time - elapsed_real

                if wait_time > 0:
                    time.sleep(wait_time)

                # 更新机器人姿态
                msg = msg_data['msg']
                self._update_robot(msg)

                # 打印进度
                if i % 30 == 0:  # 每秒打印一次（假设30Hz）
                    progress = (i + 1) / len(self.messages) * 100
                    print(f"⏱️  进度: {progress:.1f}% ({i+1}/{len(self.messages)})")

        except KeyboardInterrupt:
            print("\n⏸️  回放已停止")

        print()
        print("=" * 80)
        print("✅ 回放完成")
        print("=" * 80)

    def _update_robot(self, msg: JointState):
        """更新机器人姿态"""
        if self.robot_viz is None:
            return

        # 将关节角度转换为完整的配置向量
        q = pin.neutral(self.ik_solver.model).copy()

        # 填充受控关节的角度
        # 注意：msg.position是度，需要转换为弧度
        for i, joint_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(msg.position):
                q[joint_idx] = np.deg2rad(msg.position[i])

        # 更新可视化
        self.robot_viz.display(q)


def main():
    parser = argparse.ArgumentParser(description='在仿真环境中回放录制的视觉数据')
    parser.add_argument('bag_path', type=str, help='rosbag路径')
    parser.add_argument('--speed', type=float, default=1.0,
                       help='回放速度倍率 (默认: 1.0)')

    args = parser.parse_args()

    # 检查路径是否存在
    if not os.path.exists(args.bag_path):
        print(f"❌ 错误: 路径不存在: {args.bag_path}")
        sys.exit(1)

    # 创建回放器并开始回放
    replayer = SimulationReplayer(args.bag_path, args.speed)
    replayer.replay()

    # 保持可视化窗口打开
    print("\n💡 提示: 可视化窗口将保持打开，按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 再见!")


if __name__ == '__main__':
    main()