"""
标定计算脚本 - Calibration Solver
使用采集的数据计算手眼标定矩阵
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple

from config import CalibrationConfig


class HandEyeCalibrationSolver:
    """
    手眼标定求解器
    """

    def __init__(self, config: CalibrationConfig):
        """
        初始化标定求解器

        Args:
            config: 标定配置对象
        """
        self.config = config
        self.board = config.get_charuco_board()
        self.camera_matrix, self.dist_coeffs = config.get_camera_intrinsics()

        # 存储检测结果
        self.valid_samples = []  # 有效样本列表
        self.R_gripper2base = []  # 机械臂末端到基座的旋转矩阵列表
        self.t_gripper2base = []  # 机械臂末端到基座的平移向量列表
        self.R_target2cam = []    # 标定板到相机的旋转矩阵列表
        self.t_target2cam = []    # 标定板到相机的平移向量列表

    def detect_charuco_corners(self, image: np.ndarray) -> Tuple[bool, np.ndarray, np.ndarray]:
        """
        检测 ChArUco 角点

        Args:
            image: 输入图像

        Returns:
            tuple: (是否检测成功, 角点坐标, 角点ID)
        """
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # OpenCV 4.7.0+ 使用新的 CharucoDetector API
        charuco_params = cv2.aruco.CharucoParameters()
        detector_params = cv2.aruco.DetectorParameters()
        charuco_detector = cv2.aruco.CharucoDetector(self.board, charuco_params, detector_params)

        # 检测 ChArUco 板
        charuco_corners, charuco_ids, _, _ = charuco_detector.detectBoard(gray)

        # 至少需要 4 个角点才能进行位姿估计
        if charuco_corners is not None and len(charuco_corners) >= 4:
            return True, charuco_corners, charuco_ids

        return False, None, None

    def estimate_board_pose(self, charuco_corners: np.ndarray, charuco_ids: np.ndarray) -> Tuple[bool, np.ndarray, np.ndarray]:
        """
        估计标定板在相机坐标系下的位姿

        Args:
            charuco_corners: ChArUco 角点坐标
            charuco_ids: ChArUco 角点ID

        Returns:
            tuple: (是否成功, 旋转向量, 平移向量)
        """
        # 获取 ChArUco 板的 3D 角点坐标
        obj_points = self.board.getChessboardCorners()[charuco_ids.flatten()]

        # 使用 solvePnP 估计位姿
        success, rvec, tvec = cv2.solvePnP(
            obj_points,
            charuco_corners,
            self.camera_matrix,
            self.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        return success, rvec, tvec

    def process_all_samples(self) -> int:
        """
        处理所有采集的样本

        Returns:
            int: 有效样本数量
        """
        print("\n" + "="*60)
        print("处理采集的样本数据")
        print("="*60)

        # 读取机械臂位姿数据
        if not self.config.poses_file.exists():
            raise FileNotFoundError(f"未找到位姿文件: {self.config.poses_file}")

        robot_poses = np.load(str(self.config.poses_file))
        print(f"✓ 加载了 {len(robot_poses)} 组机械臂位姿数据")

        # 读取元数据
        metadata_file = self.config.data_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = None

        # 处理每个样本
        valid_count = 0
        for i, robot_pose in enumerate(robot_poses):
            print(f"\n处理样本 {i}...")

            # 读取图像
            if metadata:
                image_file = metadata[i]["image_file"]
            else:
                image_file = f"sample_{i:03d}.png"

            image_path = self.config.images_dir / image_file
            if not image_path.exists():
                print(f"  ⚠️ 图像文件不存在: {image_path}")
                continue

            image = cv2.imread(str(image_path))

            # 检测 ChArUco 角点
            success, charuco_corners, charuco_ids = self.detect_charuco_corners(image)

            if not success:
                print(f"  ⚠️ 未检测到足够的 ChArUco 角点")
                continue

            print(f"  ✓ 检测到 {len(charuco_corners)} 个角点")

            # 估计标定板位姿
            success, rvec, tvec = self.estimate_board_pose(charuco_corners, charuco_ids)

            if not success:
                print(f"  ⚠️ 位姿估计失败")
                continue

            print(f"  ✓ 位姿估计成功")

            # 转换旋转向量为旋转矩阵
            R_target2cam, _ = cv2.Rodrigues(rvec)

            # 提取机械臂位姿（Base to End-Effector）
            # 注意：cv2.calibrateHandEye 需要的是 gripper2base（End to Base）
            # 所以需要对 robot_pose 求逆
            T_base2end = robot_pose.reshape(4, 4)
            T_end2base = np.linalg.inv(T_base2end)

            R_gripper2base = T_end2base[:3, :3]
            t_gripper2base = T_end2base[:3, 3].reshape(3, 1)

            # 保存有效数据
            self.R_gripper2base.append(R_gripper2base)
            self.t_gripper2base.append(t_gripper2base)
            self.R_target2cam.append(R_target2cam)
            self.t_target2cam.append(tvec)

            self.valid_samples.append(i)
            valid_count += 1

        print(f"\n{'='*60}")
        print(f"✓ 处理完成: {valid_count}/{len(robot_poses)} 个有效样本")
        print(f"{'='*60}\n")

        return valid_count

    def solve_hand_eye_calibration(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        求解手眼标定

        Returns:
            tuple: (旋转矩阵, 平移向量) - 从 End-Effector 到 Camera 的变换
        """
        print("开始手眼标定计算...")

        if len(self.R_gripper2base) < 3:
            raise ValueError(f"有效样本数量不足（{len(self.R_gripper2base)}），至少需要 3 组数据")

        # 使用 cv2.calibrateHandEye 进行手眼标定
        # 注意：这是 Eye-in-Hand 配置，所以使用对应的方法
        R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
            self.R_gripper2base,
            self.t_gripper2base,
            self.R_target2cam,
            self.t_target2cam,
            method=self.config.calibration_method
        )

        # 转换为 End-Effector 到 Camera 的变换
        # calibrateHandEye 返回的是 Camera 到 Gripper 的变换
        # 我们需要的是 Gripper 到 Camera 的变换，所以需要求逆
        T_cam2gripper = np.eye(4)
        T_cam2gripper[:3, :3] = R_cam2gripper
        T_cam2gripper[:3, 3] = t_cam2gripper.flatten()

        T_gripper2cam = np.linalg.inv(T_cam2gripper)

        R_end2cam = T_gripper2cam[:3, :3]
        t_end2cam = T_gripper2cam[:3, 3].reshape(3, 1)

        print("✓ 手眼标定计算完成")

        return R_end2cam, t_end2cam

    def save_results(self, R_end2cam: np.ndarray, t_end2cam: np.ndarray):
        """
        保存标定结果

        Args:
            R_end2cam: 旋转矩阵
            t_end2cam: 平移向量
        """
        # 构建 4x4 变换矩阵
        T_end2cam = np.eye(4)
        T_end2cam[:3, :3] = R_end2cam
        T_end2cam[:3, 3] = t_end2cam.flatten()

        # 保存为 .npy 文件
        np.save(str(self.config.result_matrix_file), T_end2cam)
        print(f"✓ 变换矩阵已保存到: {self.config.result_matrix_file}")

        # 保存为 JSON 文件（便于查看）
        result_dict = {
            "T_end_to_cam": T_end2cam.tolist(),
            "rotation_matrix": R_end2cam.tolist(),
            "translation_vector": t_end2cam.flatten().tolist(),
            "valid_samples": len(self.valid_samples),
            "valid_sample_ids": self.valid_samples,
            "calibration_method": str(self.config.calibration_method)
        }

        with open(self.config.result_file, 'w') as f:
            json.dump(result_dict, f, indent=2)
        print(f"✓ 标定结果已保存到: {self.config.result_file}")

        # 打印结果
        print(f"\n{'='*60}")
        print("手眼标定结果 (T_end_to_cam):")
        print(f"{'='*60}")
        print(f"\n变换矩阵 (4x4):\n{T_end2cam}")
        print(f"\n旋转矩阵 (3x3):\n{R_end2cam}")
        print(f"\n平移向量 (3x1):\n{t_end2cam.flatten()}")
        print(f"\n平移向量 (米): x={t_end2cam[0,0]:.4f}, y={t_end2cam[1,0]:.4f}, z={t_end2cam[2,0]:.4f}")
        print(f"{'='*60}\n")

    def run(self):
        """
        运行完整的标定流程
        """
        try:
            # 1. 处理所有样本
            valid_count = self.process_all_samples()

            if valid_count < self.config.min_samples:
                print(f"⚠️ 警告: 有效样本数量 ({valid_count}) 少于推荐值 ({self.config.min_samples})")
                print("   标定精度可能不够理想，建议重新采集更多数据")

            # 2. 求解手眼标定
            R_end2cam, t_end2cam = self.solve_hand_eye_calibration()

            # 3. 保存结果
            self.save_results(R_end2cam, t_end2cam)

            print("✓ 标定流程完成!")

        except Exception as e:
            print(f"\n❌ 标定失败: {e}")
            import traceback
            traceback.print_exc()


def main():
    """
    主函数
    """
    # 加载配置
    config = CalibrationConfig()

    # 创建标定求解器
    solver = HandEyeCalibrationSolver(config)

    # 运行标定
    solver.run()


if __name__ == "__main__":
    main()