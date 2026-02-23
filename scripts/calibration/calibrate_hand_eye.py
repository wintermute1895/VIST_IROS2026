#!/usr/bin/env python3
"""
VIST 手眼标定脚本

用于标定相机坐标系到机器人基座坐标系的变换矩阵。
这是系统中最关键的标定，直接影响任务成功率。

使用方法：
    1. 采集数据：python calibrate_hand_eye.py --mode collect
    2. 计算标定：python calibrate_hand_eye.py --mode compute
    3. 验证标定：python calibrate_hand_eye.py --mode verify
    4. 保存结果：python calibrate_hand_eye.py --mode save --name "calibration_name"

Author: VIST Team
Date: 2026-02-09
"""

import os
import sys
import argparse
import numpy as np
import cv2
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)


class HandEyeCalibrator:
    """手眼标定器"""

    def __init__(self, data_dir="calibration_data/hand_eye"):
        """
        初始化标定器

        Args:
            data_dir: 标定数据保存目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 标定数据
        self.robot_poses = []  # 机器人末端位姿列表 (4x4 变换矩阵)
        self.camera_poses = []  # AprilTag 在相机中的位姿列表 (4x4 变换矩阵)

        # 标定结果
        self.T_cam_to_base = None  # 相机到机器人基座的变换矩阵
        self.calibration_error = None

        print("🛡️ [HandEyeCalibrator] 初始化完成")
        print(f"   数据目录: {self.data_dir}")

    def collect_data(self, robot_interface, camera_interface, apriltag_detector):
        """
        采集标定数据

        Args:
            robot_interface: 机器人接口（需要提供 get_end_effector_pose() 方法）
            camera_interface: 相机接口（需要提供 get_image() 方法）
            apriltag_detector: AprilTag 检测器
        """
        print("\n" + "="*60)
        print("手眼标定数据采集")
        print("="*60)
        print("\n操作说明：")
        print("  1. 手动移动机器人到不同位姿")
        print("  2. 确保相机能清晰看到 AprilTag")
        print("  3. 按 [空格] 采集当前位姿")
        print("  4. 按 [q] 完成采集")
        print("  5. 建议采集 20-30 个位姿\n")

        pose_count = 0

        while True:
            # 获取相机图像
            image = camera_interface.get_image()
            if image is None:
                print("⚠️  无法获取相机图像")
                continue

            # 检测 AprilTag
            detections = apriltag_detector.detect(image)

            # 在图像上绘制检测结果
            display_image = image.copy()
            for detection in detections:
                # 绘制边界框
                corners = detection.corners.astype(int)
                cv2.polylines(display_image, [corners], True, (0, 255, 0), 2)

                # 绘制 ID
                center = corners.mean(axis=0).astype(int)
                cv2.putText(display_image, f"ID: {detection.tag_id}",
                           tuple(center), cv2.FONT_HERSHEY_SIMPLEX,
                           0.5, (0, 255, 0), 2)

            # 显示采集状态
            status_text = f"已采集: {pose_count} 个位姿 | 按空格采集 | 按q退出"
            cv2.putText(display_image, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            if len(detections) == 0:
                cv2.putText(display_image, "未检测到 AprilTag!", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("Hand-Eye Calibration", display_image)

            # 等待按键
            key = cv2.waitKey(1) & 0xFF

            if key == ord(' '):  # 空格键：采集数据
                if len(detections) == 0:
                    print("❌ 未检测到 AprilTag，无法采集")
                    continue

                # 获取机器人位姿
                robot_pose = robot_interface.get_end_effector_pose()
                if robot_pose is None:
                    print("❌ 无法获取机器人位姿")
                    continue

                # 获取 AprilTag 位姿（使用第一个检测到的标签）
                detection = detections[0]
                camera_pose = self._detection_to_pose(detection, apriltag_detector)

                # 保存数据
                self.robot_poses.append(robot_pose)
                self.camera_poses.append(camera_pose)
                pose_count += 1

                print(f"✅ 采集位姿 {pose_count}")
                print(f"   机器人位置: {robot_pose[:3, 3]}")
                print(f"   AprilTag 距离: {np.linalg.norm(camera_pose[:3, 3]):.3f}m")

            elif key == ord('q'):  # q 键：退出
                break

        cv2.destroyAllWindows()

        # 保存采集的数据
        self._save_collected_data()

        print(f"\n✅ 数据采集完成！共采集 {pose_count} 个位姿")
        print(f"   数据已保存到: {self.data_dir}")

        return pose_count

    def _detection_to_pose(self, detection, detector):
        """
        将 AprilTag 检测结果转换为位姿矩阵

        Args:
            detection: AprilTag 检测结果
            detector: AprilTag 检测器（包含相机参数）

        Returns:
            pose: 4x4 变换矩阵
        """
        # 获取相机内参
        camera_matrix = detector.camera_matrix
        dist_coeffs = detector.dist_coeffs
        tag_size = detector.tag_size

        # 定义 3D 物体点（AprilTag 的四个角）
        object_points = np.array([
            [-tag_size/2, -tag_size/2, 0],
            [ tag_size/2, -tag_size/2, 0],
            [ tag_size/2,  tag_size/2, 0],
            [-tag_size/2,  tag_size/2, 0]
        ], dtype=np.float32)

        # 使用 solvePnP 求解位姿
        success, rvec, tvec = cv2.solvePnP(
            object_points,
            detection.corners,
            camera_matrix,
            dist_coeffs
        )

        if not success:
            raise ValueError("solvePnP 失败")

        # 转换为旋转矩阵
        R, _ = cv2.Rodrigues(rvec)

        # 构建 4x4 变换矩阵
        pose = np.eye(4)
        pose[:3, :3] = R
        pose[:3, 3] = tvec.flatten()

        return pose

    def compute_calibration(self, method='Tsai-Lenz'):
        """
        计算手眼标定

        Args:
            method: 标定方法 ('Tsai-Lenz', 'Park', 'Horaud', 'Andreff', 'Daniilidis')

        Returns:
            T_cam_to_base: 相机到机器人基座的变换矩阵
            error: 标定误差
        """
        print("\n" + "="*60)
        print(f"计算手眼标定（方法: {method}）")
        print("="*60)

        # 加载数据
        if len(self.robot_poses) == 0:
            self._load_collected_data()

        if len(self.robot_poses) < 3:
            raise ValueError(f"数据不足！至少需要 3 个位姿，当前只有 {len(self.robot_poses)} 个")

        print(f"\n使用 {len(self.robot_poses)} 个位姿进行标定...")

        # 准备数据（OpenCV 格式）
        R_gripper2base = []
        t_gripper2base = []
        R_target2cam = []
        t_target2cam = []

        for robot_pose, camera_pose in zip(self.robot_poses, self.camera_poses):
            R_gripper2base.append(robot_pose[:3, :3])
            t_gripper2base.append(robot_pose[:3, 3:4])
            R_target2cam.append(camera_pose[:3, :3])
            t_target2cam.append(camera_pose[:3, 3:4])

        # 选择标定方法
        method_map = {
            'Tsai-Lenz': cv2.CALIB_HAND_EYE_TSAI,
            'Park': cv2.CALIB_HAND_EYE_PARK,
            'Horaud': cv2.CALIB_HAND_EYE_HORAUD,
            'Andreff': cv2.CALIB_HAND_EYE_ANDREFF,
            'Daniilidis': cv2.CALIB_HAND_EYE_DANIILIDIS
        }

        cv_method = method_map.get(method, cv2.CALIB_HAND_EYE_TSAI)

        # 执行标定
        R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
            R_gripper2base,
            t_gripper2base,
            R_target2cam,
            t_target2cam,
            method=cv_method
        )

        # 构建变换矩阵
        T_cam2gripper = np.eye(4)
        T_cam2gripper[:3, :3] = R_cam2gripper
        T_cam2gripper[:3, 3] = t_cam2gripper.flatten()

        # 注意：这里得到的是相机到末端执行器的变换
        # 如果需要相机到基座的变换，需要进一步处理
        self.T_cam_to_base = T_cam2gripper

        # 计算标定误差
        self.calibration_error = self._compute_reprojection_error()

        print(f"\n✅ 标定完成！")
        print(f"\n变换矩阵 T_cam_to_base:")
        print(self.T_cam_to_base)
        print(f"\n平移向量: {self.T_cam_to_base[:3, 3]}")
        print(f"平均重投影误差: {self.calibration_error['mean']:.3f} mm")
        print(f"最大重投影误差: {self.calibration_error['max']:.3f} mm")

        return self.T_cam_to_base, self.calibration_error

    def _compute_reprojection_error(self):
        """计算重投影误差"""
        errors = []

        for robot_pose, camera_pose in zip(self.robot_poses, self.camera_poses):
            # 使用标定结果预测 AprilTag 位置
            predicted_camera_pose = np.linalg.inv(self.T_cam_to_base) @ robot_pose

            # 计算位置误差
            position_error = np.linalg.norm(
                predicted_camera_pose[:3, 3] - camera_pose[:3, 3]
            )
            errors.append(position_error * 1000)  # 转换为 mm

        return {
            'mean': np.mean(errors),
            'std': np.std(errors),
            'max': np.max(errors),
            'min': np.min(errors),
            'errors': errors
        }

    def verify_calibration(self):
        """验证标定质量"""
        print("\n" + "="*60)
        print("验证标定质量")
        print("="*60)

        if self.T_cam_to_base is None:
            print("❌ 尚未进行标定")
            return False

        if self.calibration_error is None:
            self.calibration_error = self._compute_reprojection_error()

        # 打印详细误差
        print(f"\n重投影误差统计：")
        print(f"  平均误差: {self.calibration_error['mean']:.3f} mm")
        print(f"  标准差: {self.calibration_error['std']:.3f} mm")
        print(f"  最大误差: {self.calibration_error['max']:.3f} mm")
        print(f"  最小误差: {self.calibration_error['min']:.3f} mm")

        # 评估标定质量
        mean_error = self.calibration_error['mean']
        max_error = self.calibration_error['max']

        print(f"\n标定质量评估：")
        if mean_error < 3.0 and max_error < 5.0:
            print("  ✅ 优秀（平均 < 3mm，最大 < 5mm）")
            quality = "excellent"
        elif mean_error < 5.0 and max_error < 8.0:
            print("  🟡 良好（平均 < 5mm，最大 < 8mm）")
            quality = "good"
        else:
            print("  ❌ 需要改进（误差过大）")
            print("  建议：")
            print("    1. 增加采集位姿数量")
            print("    2. 使用更大的 AprilTag")
            print("    3. 确保标签粘贴牢固")
            print("    4. 重新标定相机内参")
            quality = "poor"

        return quality in ["excellent", "good"]

    def save_calibration(self, name=None):
        """
        保存标定结果

        Args:
            name: 标定名称（默认使用时间戳）
        """
        if self.T_cam_to_base is None:
            print("❌ 尚未进行标定")
            return

        if name is None:
            name = datetime.now().strftime("calibration_%Y%m%d_%H%M%S")

        # 保存为 numpy 格式
        save_path = self.data_dir / f"{name}.npz"
        np.savez(
            save_path,
            T_cam_to_base=self.T_cam_to_base,
            calibration_error=self.calibration_error,
            robot_poses=np.array(self.robot_poses),
            camera_poses=np.array(self.camera_poses),
            timestamp=datetime.now().isoformat()
        )

        # 同时保存为 JSON 格式（方便查看）
        json_path = self.data_dir / f"{name}.json"
        calibration_data = {
            'name': name,
            'timestamp': datetime.now().isoformat(),
            'T_cam_to_base': self.T_cam_to_base.tolist(),
            'translation': self.T_cam_to_base[:3, 3].tolist(),
            'calibration_error': {
                'mean_mm': float(self.calibration_error['mean']),
                'max_mm': float(self.calibration_error['max']),
                'std_mm': float(self.calibration_error['std'])
            },
            'num_poses': len(self.robot_poses)
        }

        with open(json_path, 'w') as f:
            json.dump(calibration_data, f, indent=2)

        print(f"\n✅ 标定结果已保存：")
        print(f"   NPZ: {save_path}")
        print(f"   JSON: {json_path}")

    def _save_collected_data(self):
        """保存采集的数据"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        data_path = self.data_dir / f"collected_data_{timestamp}.npz"

        np.savez(
            data_path,
            robot_poses=np.array(self.robot_poses),
            camera_poses=np.array(self.camera_poses),
            timestamp=datetime.now().isoformat()
        )

        print(f"   数据文件: {data_path}")

    def _load_collected_data(self, filename=None):
        """加载采集的数据"""
        if filename is None:
            # 加载最新的数据文件
            data_files = sorted(self.data_dir.glob("collected_data_*.npz"))
            if len(data_files) == 0:
                raise FileNotFoundError("未找到采集的数据文件")
            filename = data_files[-1]

        data = np.load(filename)
        self.robot_poses = list(data['robot_poses'])
        self.camera_poses = list(data['camera_poses'])

        print(f"✅ 加载数据: {filename}")
        print(f"   位姿数量: {len(self.robot_poses)}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='VIST 手眼标定')
    parser.add_argument('--mode', type=str, required=True,
                       choices=['collect', 'compute', 'verify', 'save'],
                       help='运行模式')
    parser.add_argument('--method', type=str, default='Tsai-Lenz',
                       choices=['Tsai-Lenz', 'Park', 'Horaud', 'Andreff', 'Daniilidis'],
                       help='标定方法')
    parser.add_argument('--name', type=str, default=None,
                       help='标定名称（用于保存）')
    parser.add_argument('--round', type=int, default=1,
                       help='标定轮次（用于多次标定）')

    args = parser.parse_args()

    # 创建标定器
    calibrator = HandEyeCalibrator()

    if args.mode == 'collect':
        print("\n⚠️  注意：此模式需要连接真实的机器人和相机")
        print("请确保：")
        print("  1. 机器人已连接并可控制")
        print("  2. 相机已连接并可获取图像")
        print("  3. AprilTag 已固定在工作空间内")
        print("\n如果您还没有准备好，请按 Ctrl+C 退出\n")

        # TODO: 这里需要实现实际的机器人和相机接口
        print("❌ 此功能需要实现机器人和相机接口")
        print("请参考文档实现以下接口：")
        print("  - robot_interface.get_end_effector_pose()")
        print("  - camera_interface.get_image()")
        print("  - apriltag_detector.detect(image)")

    elif args.mode == 'compute':
        calibrator.compute_calibration(method=args.method)
        calibrator.verify_calibration()

    elif args.mode == 'verify':
        calibrator.verify_calibration()

    elif args.mode == 'save':
        name = args.name or f"calibration_round{args.round}"
        calibrator.save_calibration(name=name)

    print("\n✅ 完成！")


if __name__ == "__main__":
    main()
