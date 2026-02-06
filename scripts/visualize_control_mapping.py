#!/usr/bin/env python3
"""
可视化控制映射测试脚本
用于验证视觉坐标到机器人坐标的转换逻辑

功能：
1. 接收视觉节点的UDP数据
2. 通过motion_mapper进行坐标转换
3. 使用MeshCat可视化机械臂URDF模型
4. 实时显示目标位置和坐标系方向
"""

import os
import sys
import time
import socket
import json
import numpy as np
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.core.motion_mapper import ArmMotionMapper
from src.config import get_config


class ControlMappingVisualizer:
    def __init__(self):
        """初始化可视化器"""
        print("=" * 80)
        print("🎨 控制映射可视化测试")
        print("=" * 80)

        # 1. 加载配置
        print("\n📁 加载系统配置...")
        self.config = get_config()
        print("✅ 配置加载完成")

        # 2. 初始化运动映射器
        print("\n🗺️  初始化运动映射器...")
        self.mapper = ArmMotionMapper()
        print("✅ 运动映射器初始化完成")

        # 3. 初始化MeshCat可视化
        print("\n🎨 初始化MeshCat可视化...")
        self.vis = meshcat.Visualizer()
        print(f"✅ MeshCat服务器启动: {self.vis.url()}")
        print(f"   请在浏览器中打开: {self.vis.url()}")

        # 4. 设置UDP接收
        print("\n📡 设置UDP接收...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.config.udp_host, self.config.udp_port))
        self.sock.setblocking(False)
        print(f"✅ UDP接收器就绪 ({self.config.udp_host}:{self.config.udp_port})")

        # 5. 初始化可视化场景
        self._setup_scene()

        print("\n✅ 初始化完成！")
        print("\n" + "=" * 80)

    def _setup_scene(self):
        """设置可视化场景"""
        # 清空场景
        self.vis.delete()

        # ==========================================
        # 1. 添加坐标系（机器人基座坐标系）
        # ==========================================
        # 使用线段而不是圆柱体，更简单直接
        axis_length = 0.5

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

        # 添加坐标轴端点的小球，更清晰
        self.vis["robot_frame"]["x_tip"].set_object(
            g.Sphere(0.02),
            g.MeshLambertMaterial(color=0xff0000)
        )
        self.vis["robot_frame"]["x_tip"].set_transform(
            tf.translation_matrix([axis_length, 0, 0])
        )

        self.vis["robot_frame"]["y_tip"].set_object(
            g.Sphere(0.02),
            g.MeshLambertMaterial(color=0x00ff00)
        )
        self.vis["robot_frame"]["y_tip"].set_transform(
            tf.translation_matrix([0, axis_length, 0])
        )

        self.vis["robot_frame"]["z_tip"].set_object(
            g.Sphere(0.02),
            g.MeshLambertMaterial(color=0x0000ff)
        )
        self.vis["robot_frame"]["z_tip"].set_transform(
            tf.translation_matrix([0, 0, axis_length])
        )

        # ==========================================
        # 2. 添加肩部位置标记
        # ==========================================
        shoulder_pos = self.config.robot_shoulder_position
        self.vis["shoulder"].set_object(
            g.Sphere(0.03),
            g.MeshLambertMaterial(color=0xffff00)  # 黄色
        )
        self.vis["shoulder"].set_transform(
            tf.translation_matrix(shoulder_pos)
        )

        # ==========================================
        # 3. 添加目标位置标记（初始化为不可见）
        # ==========================================
        self.vis["target"]["position"].set_object(
            g.Sphere(0.02),
            g.MeshLambertMaterial(color=0xff00ff)  # 紫色
        )

        # 目标坐标系（小一点）- 使用线段，确保正交
        # 注意：这些坐标轴会随着目标位置和姿态动态更新

        # ==========================================
        # 5. 添加轨迹线（用于显示运动轨迹）
        # ==========================================
        self.trajectory_points = []
        self.max_trajectory_points = 100
        self.last_valid_pos = None  # 用于异常值检测

        # 异常值检测参数
        self.max_position_jump = 0.3  # 最大允许跳变距离（米）

        # ==========================================
        # 5. 添加文本标签（显示坐标信息）
        # ==========================================
        # MeshCat不直接支持文本，我们在终端打印

        print("\n📐 坐标系说明：")
        print("   机器人基座坐标系 (body_base_link):")
        print("   - X轴（红色）: 向前")
        print("   - Y轴（绿色）: 向左")
        print("   - Z轴（蓝色）: 向上")
        print(f"   - 肩部位置（黄色球）: {shoulder_pos}")

    def update_target(self, target_pos, target_quat):
        """更新目标位置和姿态（带异常值检测）"""
        # 异常值检测：如果跳变太大，拒绝更新
        if self.last_valid_pos is not None:
            jump_distance = np.linalg.norm(target_pos - self.last_valid_pos)
            if jump_distance > self.max_position_jump:
                print(f"⚠️ 检测到异常跳变: {jump_distance:.3f}m (阈值: {self.max_position_jump}m)，跳过此帧")
                return  # 跳过此帧，不更新可视化

        # 更新最后有效位置
        self.last_valid_pos = target_pos.copy()

        # 1. 更新目标位置球体
        self.vis["target"]["position"].set_transform(
            tf.translation_matrix(target_pos)
        )

        # 2. 更新目标坐标系（使用线段，确保正交）
        # 从四元数创建旋转矩阵
        from scipy.spatial.transform import Rotation as R
        rot = R.from_quat(target_quat)  # [x, y, z, w]
        rot_matrix = rot.as_matrix()

        axis_length = 0.15

        # 在目标坐标系中定义三个轴的方向（局部坐标）
        x_axis_local = np.array([axis_length, 0, 0])
        y_axis_local = np.array([0, axis_length, 0])
        z_axis_local = np.array([0, 0, axis_length])

        # 旋转到世界坐标系
        x_axis_world = rot_matrix @ x_axis_local
        y_axis_world = rot_matrix @ y_axis_local
        z_axis_world = rot_matrix @ z_axis_local

        # X轴 - 红色
        x_points = np.array([target_pos, target_pos + x_axis_world]).T
        self.vis["target"]["frame"]["x"].set_object(
            g.Line(g.PointsGeometry(x_points),
                   g.MeshBasicMaterial(color=0xff0000, linewidth=3))
        )

        # Y轴 - 绿色
        y_points = np.array([target_pos, target_pos + y_axis_world]).T
        self.vis["target"]["frame"]["y"].set_object(
            g.Line(g.PointsGeometry(y_points),
                   g.MeshBasicMaterial(color=0x00ff00, linewidth=3))
        )

        # Z轴 - 蓝色
        z_points = np.array([target_pos, target_pos + z_axis_world]).T
        self.vis["target"]["frame"]["z"].set_object(
            g.Line(g.PointsGeometry(z_points),
                   g.MeshBasicMaterial(color=0x0000ff, linewidth=3))
        )

        # 3. 更新轨迹
        self.trajectory_points.append(target_pos.copy())
        if len(self.trajectory_points) > self.max_trajectory_points:
            self.trajectory_points.pop(0)

        # 绘制轨迹线
        if len(self.trajectory_points) > 1:
            points = np.array(self.trajectory_points).T  # 3xN
            self.vis["trajectory"].set_object(
                g.Line(g.PointsGeometry(points),
                       g.MeshBasicMaterial(color=0x00ffff, linewidth=2))
            )

    def run(self, duration=300.0):
        """运行可视化循环"""
        print("\n🚀 开始接收数据...")
        print("   提示：")
        print("   1. 确保视觉节点正在运行")
        print(f"   2. 在浏览器中打开: {self.vis.url()}")
        print("   3. 移动手臂，观察紫色目标球和坐标系的变化")
        print("   4. 按 Ctrl+C 停止\n")

        start_time = time.time()
        frame_count = 0
        last_print_time = time.time()

        try:
            while time.time() - start_time < duration:
                # 接收UDP数据
                try:
                    data, _ = self.sock.recvfrom(self.config.udp_buffer_size)
                    packet = json.loads(data.decode('utf-8'))

                    if 'keypoints' in packet:
                        human_kps = packet['keypoints']
                    else:
                        human_kps = packet

                    # 检查关键点是否完整
                    if 'wrist' not in human_kps or 'elbow' not in human_kps:
                        time.sleep(0.01)
                        continue

                    # 运动映射
                    result = self.mapper.human_to_robot(human_kps)
                    if result is None:
                        time.sleep(0.01)
                        continue

                    target_pos, target_quat, debug_info = result

                    # 更新可视化
                    self.update_target(target_pos, target_quat)

                    frame_count += 1

                    # 每秒打印一次状态
                    if time.time() - last_print_time >= 1.0:
                        print(f"✅ 帧数: {frame_count} | "
                              f"目标位置: [{target_pos[0]:.3f}, {target_pos[1]:.3f}, {target_pos[2]:.3f}] | "
                              f"轨迹点数: {len(self.trajectory_points)}")
                        last_print_time = time.time()

                except BlockingIOError:
                    # 没有数据，继续等待
                    time.sleep(0.01)
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析错误: {e}")
                except Exception as e:
                    print(f"⚠️ 处理数据时出错: {e}")
                    import traceback
                    traceback.print_exc()

        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")

        finally:
            self.sock.close()
            print(f"\n📊 统计:")
            print(f"   总帧数: {frame_count}")
            print(f"   运行时长: {time.time() - start_time:.1f}秒")
            print(f"   平均帧率: {frame_count / (time.time() - start_time):.1f} fps")
            print("\n✅ 可视化器已退出")


def main():
    visualizer = ControlMappingVisualizer()
    visualizer.run(duration=300.0)  # 运行5分钟


if __name__ == "__main__":
    main()
