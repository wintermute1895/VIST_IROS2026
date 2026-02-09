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
from robot_interface import RobotInterface, MockRobotInterface


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

        # 配置彩色流（640x480 @ 30fps）
        self.rs_config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        print("正在启动 RealSense D405 相机...")
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

        # 阈值设置
        MIN_POSITION_CHANGE = 0.02  # 2cm
        MIN_ROTATION_CHANGE = 0.1   # 旋转矩阵差异

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
        # 保存图像
        image_filename = f"sample_{sample_id:03d}.png"
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
        metadata_file = self.config.data_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self.collected_data, f, indent=2)
        print(f"✓ 元数据已保存到: {metadata_file}")

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
        print("  - 按 's' 键: 保存当前图像和机械臂位姿")
        print("  - 按 'q' 键: 退出采集")
        print(f"  - 最少需要采集 {self.config.min_samples} 组数据")
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
                info_text = f"Samples: {sample_count}/{self.config.min_samples}"
                cv2.putText(display_image, info_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                if sample_count < self.config.min_samples:
                    status_text = "Press 's' to capture"
                    color = (0, 165, 255)  # 橙色
                else:
                    status_text = "Ready! Press 'q' to finish"
                    color = (0, 255, 0)  # 绿色

                cv2.putText(display_image, status_text, (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                cv2.imshow("Data Collection - RealSense D405", display_image)

                # 处理按键
                key = cv2.waitKey(1) & 0xFF

                if key == ord('s'):
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

                        print(f"进度: {sample_count}/{self.config.min_samples}\n")

                    except Exception as e:
                        print(f"⚠️ 获取机械臂位姿失败: {e}")
                        print("   请检查机械臂连接和接口实现\n")

                elif key == ord('q'):
                    if sample_count < self.config.min_samples:
                        print(f"\n⚠️ 警告: 当前只采集了 {sample_count} 组数据")
                        print(f"   建议至少采集 {self.config.min_samples} 组数据以获得更好的标定精度")
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

    # 创建机械臂接口
    # ⚠️ 注意：这里使用 Mock 接口进行测试
    # 实际使用时，请替换为你自己的机械臂接口实现
    print("⚠️ 当前使用 真实 Robot Interface（测试模式）")
    print("   实际使用时，请在代码中设定为你的机械臂接口\n")

    # robot = MockRobotInterface()

    # 如果你已经实现了自己的机械臂接口，请取消下面的注释：
    from robot_interface import YourRobotInterface
    robot = YourRobotInterface()

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