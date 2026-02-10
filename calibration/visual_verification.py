"""
可视化验证脚本 - Visual Verification
用于验证手眼标定的精度，通过重投影误差评估标定质量
"""

import cv2
import numpy as np
import pyrealsense2 as rs
from pathlib import Path

from config import CalibrationConfig
from robot_interface import RobotInterface, MockRobotInterface


class CalibrationVerifier:
    """
    标定验证器
    通过重投影验证手眼标定精度
    """

    def __init__(self, config: CalibrationConfig, robot: RobotInterface):
        """
        初始化验证器

        Args:
            config: 标定配置对象
            robot: 机械臂接口对象
        """
        self.config = config
        self.robot = robot
        self.board = config.get_charuco_board()
        self.camera_matrix, self.dist_coeffs = config.get_camera_intrinsics()

        # 加载手眼标定结果
        self.T_end2cam = self.load_calibration_result()

        # 初始化 RealSense 相机
        self.pipeline = rs.pipeline()
        self.rs_config = rs.config()
        self.rs_config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)

        print("正在启动 RealSense D405 相机...")
        self.pipeline.start(self.rs_config)
        print("✓ 相机启动成功")

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
        print(f"✓ 加载手眼标定矩阵:\n{T_end2cam}\n")
        return T_end2cam

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

        color_image = np.asanyarray(color_frame.get_data())
        return color_image

    def detect_charuco_board(self, image: np.ndarray):
        """
        检测 ChArUco 标定板并估计位姿

        Args:
            image: 输入图像

        Returns:
            tuple: (是否成功, 旋转向量, 平移向量, 角点坐标, 角点ID)
        """
        # 转换为灰度图
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # OpenCV 4.7.0+ 使用新的 CharucoDetector API
        charuco_params = cv2.aruco.CharucoParameters()
        detector_params = cv2.aruco.DetectorParameters()
        charuco_detector = cv2.aruco.CharucoDetector(self.board, charuco_params, detector_params)

        # 检测 ChArUco 板
        charuco_corners, charuco_ids, _, _ = charuco_detector.detectBoard(gray)

        if charuco_corners is not None and len(charuco_corners) >= 4:
            # 估计标定板位姿
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

            if success:
                return True, rvec, tvec, charuco_corners, charuco_ids

        return False, None, None, None, None

    def reproject_board_origin(self, rvec_board2cam: np.ndarray, tvec_board2cam: np.ndarray,
                               T_base2end: np.ndarray) -> np.ndarray:
        """
        重投影标定板原点到图像平面

        坐标系转换流程（这是验证的核心）：
        1. 标定板原点在相机坐标系下的位置: P_cam = tvec_board2cam
        2. 相机在末端执行器坐标系下的位置: P_end = T_end2cam^(-1) * P_cam
        3. 末端执行器在基座坐标系下的位置: P_base = T_base2end * P_end
        4. 反向投影: P_base -> P_end -> P_cam -> 图像像素坐标

        Args:
            rvec_board2cam: 标定板到相机的旋转向量
            tvec_board2cam: 标定板到相机的平移向量
            T_base2end: 基座到末端执行器的变换矩阵 (4x4)

        Returns:
            np.ndarray: 图像像素坐标 [u, v]
        """
        # ==================== 步骤 1: 标定板原点在相机坐标系下的位置 ====================
        # 标定板原点 (0, 0, 0) 在相机坐标系下的坐标就是 tvec_board2cam
        P_board_origin = np.array([[0], [0], [0], [1]], dtype=np.float64)  # 齐次坐标

        # 构建标定板到相机的变换矩阵
        R_board2cam, _ = cv2.Rodrigues(rvec_board2cam)
        T_board2cam = np.eye(4)
        T_board2cam[:3, :3] = R_board2cam
        T_board2cam[:3, 3] = tvec_board2cam.flatten()

        # 标定板原点在相机坐标系下的位置
        P_cam = T_board2cam @ P_board_origin
        P_cam = P_cam[:3]  # 转换为非齐次坐标

        # ==================== 步骤 2: 通过手眼矩阵转换到末端执行器坐标系 ====================
        # T_end2cam: 末端执行器到相机的变换
        # 我们需要 T_cam2end: 相机到末端执行器的变换
        T_cam2end = np.linalg.inv(self.T_end2cam)

        # 将相机坐标系下的点转换到末端执行器坐标系
        P_cam_homo = np.vstack([P_cam, [1]])  # 转换为齐次坐标
        P_end = T_cam2end @ P_cam_homo
        P_end = P_end[:3]  # 转换为非齐次坐标

        # ==================== 步骤 3: 转换到基座坐标系 ====================
        # T_base2end: 基座到末端执行器的变换
        P_end_homo = np.vstack([P_end, [1]])
        P_base = T_base2end @ P_end_homo
        P_base = P_base[:3]

        # ==================== 步骤 4: 反向投影回图像平面 ====================
        # 现在我们有了标定板原点在基座坐标系下的位置
        # 反向转换: P_base -> P_end -> P_cam -> 图像像素

        # 4.1: 基座 -> 末端执行器
        T_end2base = np.linalg.inv(T_base2end)
        P_base_homo = np.vstack([P_base, [1]])
        P_end_reprojected = T_end2base @ P_base_homo
        P_end_reprojected = P_end_reprojected[:3]

        # 4.2: 末端执行器 -> 相机
        P_end_reprojected_homo = np.vstack([P_end_reprojected, [1]])
        P_cam_reprojected = self.T_end2cam @ P_end_reprojected_homo
        P_cam_reprojected = P_cam_reprojected[:3]

        # 4.3: 相机坐标系 -> 图像像素坐标
        # 使用相机内参矩阵投影
        # [u, v, 1]^T = K * [X, Y, Z]^T / Z
        pixel_coords = self.camera_matrix @ P_cam_reprojected
        pixel_coords = pixel_coords / pixel_coords[2]  # 归一化

        u, v = int(pixel_coords[0]), int(pixel_coords[1])

        return np.array([u, v])

    def draw_board_axes(self, image: np.ndarray, rvec: np.ndarray, tvec: np.ndarray):
        """
        在图像上绘制标定板坐标轴

        Args:
            image: 输入图像
            rvec: 旋转向量
            tvec: 平移向量
        """
        # 绘制坐标轴（长度为 square_size）
        axis_length = self.config.charuco_board.square_size
        cv2.drawFrameAxes(image, self.camera_matrix, self.dist_coeffs,
                         rvec, tvec, axis_length, 3)

    def run(self):
        """
        运行验证流程
        """
        print("\n" + "="*60)
        print("Eye-in-Hand 标定验证")
        print("="*60)
        print("验证说明:")
        print("  - 绿色角点: 检测到的 ChArUco 角点")
        print("  - RGB 坐标轴: 标定板坐标系（红=X, 绿=Y, 蓝=Z）")
        print("  - 红色圆点: 重投影的标定板原点")
        print("\n验证方法:")
        print("  1. 移动机械臂到不同位置")
        print("  2. 观察红色圆点是否始终跟随标定板原点")
        print("  3. 如果红点偏离较大，说明标定精度不够")
        print("\n操作:")
        print("  - 按 'q' 键: 退出验证")
        print("="*60 + "\n")

        try:
            while True:
                # 捕获图像
                image = self.capture_frame()
                if image is None:
                    continue

                display_image = image.copy()

                # 检测标定板
                success, rvec, tvec, charuco_corners, charuco_ids = self.detect_charuco_board(image)

                if success:
                    # 绘制检测到的角点
                    cv2.aruco.drawDetectedCornersCharuco(
                        display_image, charuco_corners, charuco_ids,
                        self.config.validation.detected_corner_color
                    )

                    # 绘制标定板坐标轴
                    self.draw_board_axes(display_image, rvec, tvec)

                    # 获取当前机械臂位姿
                    try:
                        T_base2end = self.robot.get_current_pose()

                        # 重投影标定板原点
                        reprojected_point = self.reproject_board_origin(rvec, tvec, T_base2end)

                        # 绘制重投影点（红色圆点）
                        cv2.circle(
                            display_image,
                            tuple(reprojected_point),
                            self.config.validation.reprojection_point_radius,
                            self.config.validation.reprojection_point_color,
                            -1  # 填充
                        )

                        # 绘制十字线（更明显）
                        cv2.drawMarker(
                            display_image,
                            tuple(reprojected_point),
                            self.config.validation.reprojection_point_color,
                            cv2.MARKER_CROSS,
                            20,
                            2
                        )

                        # 计算重投影误差（像素）
                        # 标定板原点在图像上的真实位置
                        board_origin_3d = np.array([[0], [0], [0]], dtype=np.float64)
                        projected_origin, _ = cv2.projectPoints(
                            board_origin_3d, rvec, tvec,
                            self.camera_matrix, self.dist_coeffs
                        )
                        true_point = projected_origin[0][0]

                        error = np.linalg.norm(reprojected_point - true_point)

                        # 显示误差信息
                        cv2.putText(
                            display_image,
                            f"Reprojection Error: {error:.2f} px",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            (0, 255, 255),  # 黄色
                            2
                        )

                        # 显示精度评估
                        if error < 5:
                            status = "Excellent"
                            color = (0, 255, 0)  # 绿色
                        elif error < 10:
                            status = "Good"
                            color = (0, 165, 255)  # 橙色
                        else:
                            status = "Poor - Recalibrate!"
                            color = (0, 0, 255)  # 红色

                        cv2.putText(
                            display_image,
                            f"Calibration Quality: {status}",
                            (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7,
                            color,
                            2
                        )

                    except Exception as e:
                        cv2.putText(
                            display_image,
                            f"Robot Error: {str(e)[:40]}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 0, 255),
                            2
                        )

                else:
                    # 未检测到标定板
                    cv2.putText(
                        display_image,
                        "ChArUco Board Not Detected",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2
                    )

                # 显示图像
                cv2.imshow("Calibration Verification - RealSense D405", display_image)

                # 处理按键
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("\n退出验证")
                    break

        finally:
            # 清理资源
            cv2.destroyAllWindows()
            self.pipeline.stop()
            print("✓ 相机已关闭")


def main():
    """
    主函数
    """
    # 加载配置
    config = CalibrationConfig()

    # 创建机械臂接口
    print("⚠️ 当前使用 Mock Robot Interface（测试模式）")
    print("   实际使用时，请在代码中替换为你的机械臂接口\n")

    robot = MockRobotInterface()

    # 如果你已经实现了自己的机械臂接口，请取消下面的注释：
    # from robot_interface import YourRobotInterface
    # robot = YourRobotInterface()

    # 创建验证器
    try:
        verifier = CalibrationVerifier(config, robot)
        verifier.run()
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()