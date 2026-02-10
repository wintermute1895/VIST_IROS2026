"""
标定误差分析脚本 - Calibration Error Analysis
分析手眼标定的精度，计算重投影误差统计
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import List, Tuple

from config import CalibrationConfig


class CalibrationErrorAnalyzer:
    """
    标定误差分析器
    """

    def __init__(self, config: CalibrationConfig):
        """
        初始化误差分析器

        Args:
            config: 标定配置对象
        """
        self.config = config
        self.board = config.get_charuco_board()
        self.camera_matrix, self.dist_coeffs = config.get_camera_intrinsics()

        # 加载手眼标定结果
        self.T_end2cam = self.load_calibration_result()

        # 加载标定数据
        self.robot_poses = self.load_robot_poses()
        self.num_samples = len(self.robot_poses)

    def load_calibration_result(self) -> np.ndarray:
        """
        加载手眼标定结果

        Returns:
            np.ndarray: 4x4 变换矩阵 (T_end_to_cam)
        """
        if not self.config.result_matrix_file.exists():
            raise FileNotFoundError(
                f"未找到标定结果文件: {self.config.result_matrix_file}\n"
                f"请先运行 calibration_solver.py 进行标定"
            )

        T_end2cam = np.load(str(self.config.result_matrix_file))
        print(f"✓ 加载手眼标定矩阵: {self.config.result_matrix_file}\n")
        return T_end2cam

    def load_robot_poses(self) -> np.ndarray:
        """
        加载机械臂位姿数据

        Returns:
            np.ndarray: 机械臂位姿数组 (N, 4, 4)
        """
        if not self.config.poses_file.exists():
            raise FileNotFoundError(f"未找到位姿文件: {self.config.poses_file}")

        robot_poses = np.load(str(self.config.poses_file))
        print(f"✓ 加载了 {len(robot_poses)} 组机械臂位姿数据\n")
        return robot_poses

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

    def calculate_reprojection_error(self, rvec_board2cam: np.ndarray, tvec_board2cam: np.ndarray,
                                    T_base2end: np.ndarray, charuco_corners: np.ndarray,
                                    charuco_ids: np.ndarray) -> float:
        """
        计算重投影误差

        Args:
            rvec_board2cam: 标定板到相机的旋转向量
            tvec_board2cam: 标定板到相机的平移向量
            T_base2end: 基座到末端执行器的变换矩阵
            charuco_corners: 检测到的角点坐标
            charuco_ids: 角点ID

        Returns:
            float: 平均重投影误差（像素）
        """
        # 方法1: 直接使用检测到的角点计算重投影误差
        # 将 3D 角点投影到图像平面
        obj_points = self.board.getChessboardCorners()[charuco_ids.flatten()]

        # 使用标定板位姿投影角点
        projected_points, _ = cv2.projectPoints(
            obj_points,
            rvec_board2cam,
            tvec_board2cam,
            self.camera_matrix,
            self.dist_coeffs
        )

        # 计算重投影误差
        errors = np.linalg.norm(charuco_corners - projected_points.reshape(-1, 2), axis=1)
        mean_error = np.mean(errors)

        return mean_error

    def analyze_all_samples(self) -> dict:
        """
        分析所有标定样本的误差

        Returns:
            dict: 误差统计信息
        """
        print("=" * 60)
        print("分析标定误差")
        print("=" * 60)

        errors = []
        valid_samples = 0
        failed_samples = 0

        for i in range(self.num_samples):
            # 读取图像
            image_file = self.config.images_dir / f"sample_{i:03d}.png"

            if not image_file.exists():
                print(f"样本 {i}: 图像文件不存在，跳过")
                failed_samples += 1
                continue

            image = cv2.imread(str(image_file))
            if image is None:
                print(f"样本 {i}: 无法读取图像，跳过")
                failed_samples += 1
                continue

            # 检测 ChArUco 角点
            success, charuco_corners, charuco_ids = self.detect_charuco_corners(image)

            if not success:
                print(f"样本 {i}: 未检测到足够的角点，跳过")
                failed_samples += 1
                continue

            # 估计标定板位姿
            success, rvec, tvec = self.estimate_board_pose(charuco_corners, charuco_ids)

            if not success:
                print(f"样本 {i}: 位姿估计失败，跳过")
                failed_samples += 1
                continue

            # 计算重投影误差
            T_base2end = self.robot_poses[i]
            error = self.calculate_reprojection_error(
                rvec, tvec, T_base2end, charuco_corners, charuco_ids
            )

            errors.append(error)
            valid_samples += 1

            print(f"样本 {i}: 重投影误差 = {error:.3f} 像素")

        print("\n" + "=" * 60)
        print("误差统计")
        print("=" * 60)

        if len(errors) == 0:
            print("❌ 没有有效样本可以分析")
            return None

        errors = np.array(errors)

        stats = {
            "total_samples": self.num_samples,
            "valid_samples": valid_samples,
            "failed_samples": failed_samples,
            "mean_error": float(np.mean(errors)),
            "std_error": float(np.std(errors)),
            "min_error": float(np.min(errors)),
            "max_error": float(np.max(errors)),
            "median_error": float(np.median(errors)),
            "errors": errors.tolist()
        }

        return stats

    def print_statistics(self, stats: dict):
        """
        打印误差统计信息

        Args:
            stats: 误差统计字典
        """
        if stats is None:
            return

        print(f"\n总样本数: {stats['total_samples']}")
        print(f"有效样本数: {stats['valid_samples']}")
        print(f"失败样本数: {stats['failed_samples']}")
        print(f"\n重投影误差统计（像素）:")
        print(f"  平均值: {stats['mean_error']:.3f}")
        print(f"  标准差: {stats['std_error']:.3f}")
        print(f"  最小值: {stats['min_error']:.3f}")
        print(f"  最大值: {stats['max_error']:.3f}")
        print(f"  中位数: {stats['median_error']:.3f}")

        # 精度评估
        print(f"\n标定质量评估:")
        mean_error = stats['mean_error']
        if mean_error < self.config.validation.excellent_threshold:
            quality = "优秀 (Excellent)"
            color_code = "✓"
        elif mean_error < self.config.validation.good_threshold:
            quality = "良好 (Good)"
            color_code = "✓"
        elif mean_error < self.config.validation.acceptable_threshold:
            quality = "可接受 (Acceptable)"
            color_code = "⚠"
        else:
            quality = "较差 (Poor) - 建议重新标定"
            color_code = "❌"

        print(f"  {color_code} {quality}")
        print(f"  平均误差: {mean_error:.3f} 像素")

        # 保存统计结果
        with open(self.config.error_stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"\n✓ 误差统计已保存到: {self.config.error_stats_file}")

    def run(self):
        """
        运行误差分析
        """
        print("\n" + "=" * 60)
        print("手眼标定误差分析")
        print("=" * 60)
        print()

        # 分析所有样本
        stats = self.analyze_all_samples()

        # 打印统计信息
        self.print_statistics(stats)

        print("\n" + "=" * 60)


def main():
    """
    主函数
    """
    try:
        # 加载配置
        config = CalibrationConfig()

        # 创建误差分析器
        analyzer = CalibrationErrorAnalyzer(config)

        # 运行分析
        analyzer.run()

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

