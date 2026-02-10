"""
数据采集脚本 - Data Collection
用于采集手眼标定所需的图像和机械臂位姿数据
"""

import cv2
import numpy as np
import pyrealsense2 as rs
from pathlib import Path
from datetime import datetime
import json

from config import CalibrationConfig
from robot_interface import RobotInterface, MockRobotInterface, LinkerArmInterface


class DataCollector:
    """
    数据采集器
    负责采集图像和机械臂位姿
    """

    def __init__(self, config: CalibrationConfig, robot: RobotInterface):
        """
        初始化数据采集器

        Args:
            config: 标定配置对象
            robot: 机械臂接口对象
        """
        self.config = config
        self.robot = robot
        self.collected_data = []  # 存储采集的数据
        self.collected_poses = []  # 存储已采集的位姿矩阵（用于检测变化）

        # 初始化 RealSense 相机
        self.pipeline = rs.pipeline()
        self.rs_config = rs.config()

        # 从配置读取相机参数
        self.rs_config.enable_stream(
            rs.stream.color,
            config.camera.width,
            config.camera.height,
            rs.format.bgr8,
            config.camera.fps
        )

        print(f"正在启动 {config.camera.camera_type} 相机...")
        print(f"  分辨率: {config.camera.width}x{config.camera.height} @ {config.camera.fps}fps")

        # 硬件复位（如果启用）
        if config.camera.enable_hardware_reset:
            try:
                ctx = rs.context()
                devices = ctx.query_devices()
                for dev in devices:
                    dev.hardware_reset()
                print("  ✓ 相机硬件复位成功")
            except Exception as e:
                print(f"  ⚠️ 相机硬件复位失败: {e}")

        self.pipeline.start(self.rs_config)
        print("✓ 相机启动成功")

    def capture_frame(self):
        """
        从相机捕获一帧图像

        Returns:
            np.ndarray: BGR 图像
        """
        frames = self.pipeline.wait_for_frames()
        color_frame = frames.get_color_frame()

        if not color_frame:
            return None

        # 转换为 numpy 数组
        color_image = np.asanyarray(color_frame.get_data())
        return color_image

    def check_pose_variation(self, new_pose: np.ndarray) -> tuple[bool, str]:
        """
        检查新位姿与已采集位姿的变化是否足够

        Args:
            new_pose: 新的机械臂位姿（4x4 矩阵）

        Returns:
            tuple: (是否足够不同, 提示信息)
        """
        if len(self.collected_poses) == 0:
            return True, "第一个位姿"

        # 计算与所有已采集位姿的距离
        min_position_dist = float('inf')
        min_rotation_dist = float('inf')

        new_position = new_pose[:3, 3]
        new_rotation = new_pose[:3, :3]

        for old_pose in self.collected_poses:
            old_position = old_pose[:3, 3]
            old_rotation = old_pose[:3, :3]

            # 位置距离（欧氏距离）
            position_dist = np.linalg.norm(new_position - old_position)
            min_position_dist = min(min_position_dist, position_dist)

            # 旋转距离（Frobenius 范数）
            rotation_dist = np.linalg.norm(new_rotation - old_rotation, 'fro')
            min_rotation_dist = min(min_rotation_dist, rotation_dist)

        # 从配置读取阈值
        MIN_POSITION_CHANGE = self.config.data_collection.min_position_change
        MIN_ROTATION_CHANGE = self.config.data_collection.min_rotation_change

        if min_position_dist < MIN_POSITION_CHANGE and min_rotation_dist < MIN_ROTATION_CHANGE:
            return False, f"⚠️  位姿变化过小 (位置: {min_position_dist*1000:.1f}mm, 旋转: {min_rotation_dist:.3f})"
        else:
            return True, f"✓ 位姿变化足够 (位置: {min_position_dist*1000:.1f}mm, 旋转: {min_rotation_dist:.3f})"

    def save_sample(self, image: np.ndarray, robot_pose: np.ndarray, sample_id: int):
        """
        保存一组样本数据

        Args:
            image: 图像
            robot_pose: 机械臂位姿（4x4 矩阵）
            sample_id: 样本编号
        """
        # 使用配置中的文件格式
        image_filename = f"{self.config.storage.image_prefix}{sample_id:03d}.{self.config.storage.image_format}"
        image_path = self.config.images_dir / image_filename
        cv2.imwrite(str(image_path), image)

        # 保存位姿信息
        self.collected_data.append({
            "sample_id": sample_id,
            "image_file": image_filename,
            "robot_pose": robot_pose.tolist(),  # 转换为列表以便 JSON 序列化
            "timestamp": datetime.now().isoformat()
        })

        print(f"✓ 已保存样本 {sample_id}: {image_filename}")

    def save_all_data(self):
        """
        保存所有采集的数据到文件
        """
        # 保存机械臂位姿数组
        poses_array = np.array([data["robot_pose"] for data in self.collected_data])
        np.save(str(self.config.poses_file), poses_array)
        print(f"✓ 机械臂位姿已保存到: {self.config.poses_file}")

        # 保存元数据（JSON 格式）
        with open(self.config.metadata_file, 'w') as f:
            json.dump(self.collected_data, f, indent=2)
        print(f"✓ 元数据已保存到: {self.config.metadata_file}")

        # 分析位姿变化
        self.analyze_pose_variation(poses_array)

    def analyze_pose_variation(self, poses: np.ndarray):
        """
        分析采集的位姿变化情况

        Args:
            poses: 位姿数组 (N, 4, 4)
        """
        print(f"\n{'='*60}")
        print("位姿变化分析")
        print(f"{'='*60}")

        if len(poses) < 2:
            print("样本数量不足，无法分析")
            return

        # 提取位置和旋转
        positions = poses[:, :3, 3]

        # 计算位置变化范围
        print(f"\n位置变化范围（米）:")
        print(f"  X: [{positions[:, 0].min():.3f}, {positions[:, 0].max():.3f}]  变化: {positions[:, 0].max() - positions[:, 0].min():.3f}")
        print(f"  Y: [{positions[:, 1].min():.3f}, {positions[:, 1].max():.3f}]  变化: {positions[:, 1].max() - positions[:, 1].min():.3f}")
        print(f"  Z: [{positions[:, 2].min():.3f}, {positions[:, 2].max():.3f}]  变化: {positions[:, 2].max() - positions[:, 2].min():.3f}")

        # 计算相邻位姿间距
        distances = []
        for i in range(len(poses) - 1):
            dist = np.linalg.norm(positions[i] - positions[i+1])
            distances.append(dist)

        print(f"\n相邻位姿间距（米）:")
        print(f"  平均: {np.mean(distances):.3f}")
        print(f"  最小: {np.min(distances):.3f}")
        print(f"  最大: {np.max(distances):.3f}")

        # 检查是否所有位姿相同
        all_same = True
        for i in range(1, len(poses)):
            if not np.allclose(poses[0], poses[i], atol=1e-6):
                all_same = False
                break

        if all_same:
            print(f"\n❌ 警告：所有位姿完全相同！")
            print(f"   这会导致手眼标定失败")
            print(f"   请使用真实机械臂并移动到不同位置重新采集")
        elif np.mean(distances) < 0.01:
            print(f"\n⚠️  警告：位姿变化较小（平均间距 < 1cm）")
            print(f"   建议增加位姿变化范围以提高标定精度")
        else:
            print(f"\n✓ 位姿变化良好")

        print(f"{'='*60}\n")

    def run(self):
        """
        运行数据采集流程
        """
        print("\n" + "="*60)
        print("Eye-in-Hand 数据采集")
        print("="*60)
        print("操作说明:")
        print(f"  - 按 '{self.config.data_collection.capture_key}' 键: 保存当前图像和机械臂位姿")
        print(f"  - 按 '{self.config.data_collection.quit_key}' 键: 退出采集")
        print(f"  - 最少需要采集 {self.config.data_collection.min_samples} 组数据")
        print("\n采集建议:")
        print("  1. 移动机械臂到不同位置和姿态")
        print("  2. 确保标定板在相机视野内且清晰可见")
        print("  3. 尽量覆盖工作空间的不同区域")
        print("  4. 避免位姿过于相似的数据")
        print("="*60 + "\n")

        sample_count = 0

        try:
            while True:
                # 捕获图像
                image = self.capture_frame()
                if image is None:
                    continue

                # 显示图像
                display_image = image.copy()

                # 添加信息文本
                info_text = f"Samples: {sample_count}/{self.config.data_collection.min_samples}"
                cv2.putText(display_image, info_text, (10, 30),
                           self.config.data_collection.font_face, self.config.data_collection.font_scale,
                           self.config.data_collection.text_color_info, self.config.data_collection.font_thickness)
                if sample_count < self.config.data_collection.min_samples:
                    status_text = f"Press '{self.config.data_collection.capture_key}' to capture"
                    color = self.config.data_collection.text_color_warning
                else:
                    status_text = f"Ready! Press '{self.config.data_collection.quit_key}' to finish"
                    color = self.config.data_collection.text_color_info

                cv2.putText(display_image, status_text, (10, 70),
                           self.config.data_collection.font_face, 0.7, color,
                           self.config.data_collection.font_thickness)
                cv2.imshow(self.config.data_collection.window_name, display_image)

                # 处理按键
                key = cv2.waitKey(1) & 0xFF

                if key == ord(self.config.data_collection.capture_key):
                    # 获取当前机械臂位姿
                    try:
                        robot_pose = self.robot.get_current_pose()
                        print(f"\n机械臂位姿:\n{robot_pose}")

                        # 检查位姿变化
                        is_different, message = self.check_pose_variation(robot_pose)
                        print(f"位姿检查: {message}")

                        if not is_different and len(self.collected_poses) > 0:
                            print("   建议移动机械臂到更不同的位置")
                            print("   是否仍要保存此位姿? (y/n): ", end='')
                            confirm = input().strip().lower()
                            if confirm != 'y':
                                print("已跳过此位姿\n")
                                continue

                        # 保存样本
                        self.save_sample(image, robot_pose, sample_count)
                        self.collected_poses.append(robot_pose)
                        sample_count += 1

                        print(f"进度: {sample_count}/{self.config.data_collection.min_samples}\n")

                    except Exception as e:
                        print(f"⚠️ 获取机械臂位姿失败: {e}")
                        print("   请检查机械臂连接和接口实现\n")

                elif key == ord(self.config.data_collection.quit_key):
                    if sample_count < self.config.data_collection.min_samples:
                        print(f"\n⚠️ 警告: 当前只采集了 {sample_count} 组数据")
                        print(f"   建议至少采集 {self.config.data_collection.min_samples} 组数据以获得更好的标定精度")
                        print("   是否确认退出? (y/n): ", end='')

                        # 等待用户确认
                        confirm = input().strip().lower()
                        if confirm != 'y':
                            print("继续采集...\n")
                            continue

                    print(f"\n采集完成! 共采集 {sample_count} 组数据")
                    break


        finally:
            # 保存所有数据
            if sample_count > 0:
                self.save_all_data()

            # 清理资源
            cv2.destroyAllWindows()
            self.pipeline.stop()
            print("\n✓ 相机已关闭")
            print("✓ 数据采集完成")


def main():
    """
    主函数
    """
    # 加载配置
    config = CalibrationConfig()
    config.print_config()

    # 创建机械臂接口 - LinkerArm (LBot)
    print("正在连接 LinkerArm 机械臂...")
    print(f"  IP: {config.robot.tcp_host}")
    print(f"  使用机械臂: {config.robot.arm_side}\n")

    # 获取 SDK 路径
    sdk_path = config.get_sdk_path()

    robot = LinkerArmInterface(
        tcp_host=config.robot.tcp_host,
        arm_side=config.robot.arm_side,
        sdk_path=str(sdk_path),
        move_speed=config.robot.move_speed,
        move_accel=config.robot.move_accel,
        move_block=config.robot.move_block
    )

    # 创建数据采集器
    try:
        collector = DataCollector(config, robot)
        collector.run()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()