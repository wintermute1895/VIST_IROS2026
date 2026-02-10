"""
Eye-in-Hand Calibration Configuration
配置文件：包含所有标定相关的参数
支持分层配置、参数验证、配置文件加载
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import json
import yaml


# ==================== 机器人配置 ====================

@dataclass
class RobotConfig:
    """机器人配置"""
    # 连接参数
    tcp_host: str = "192.168.10.21"  # 机器人控制器 IP 地址
    arm_side: str = "right"  # 使用的机械臂：left 或 right

    # SDK 路径配置
    sdk_relative_path: str = "src/robot/sdk/linkerarm"  # 相对于项目根目录的 SDK 路径
    sdk_search_paths: list = field(default_factory=lambda: [
        "src/robot/sdk/linkerarm",
        "../src/robot/sdk/linkerarm",
        "/home/luka/.ssh/VIST/src/robot/sdk/linkerarm",
    ])  # SDK 搜索路径列表

    # 运动控制参数
    move_speed: float = 0.3  # 运动速度 (m/s)
    move_accel: float = 0.1  # 加速度 (m/s²)
    move_block: bool = True  # 是否阻塞等待运动完成

    # 连接超时
    connection_timeout: float = 10.0  # 连接超时时间（秒）


# ==================== 相机配置 ====================

@dataclass
class CameraConfig:
    """相机配置"""
    # 相机类型
    camera_type: str = "realsense_d405"  # 相机类型标识

    # 分辨率和帧率
    width: int = 640  # 图像宽度
    height: int = 480  # 图像高度
    fps: int = 30  # 帧率

    # 内参配置
    use_auto_intrinsics: bool = True  # 是否自动从相机读取内参

    # 手动内参（当 use_auto_intrinsics=False 时使用）
    fx: float = 615.0  # 焦距 x
    fy: float = 615.0  # 焦距 y
    cx: float = 320.0  # 主点 x
    cy: float = 240.0  # 主点 y
    distortion_coeffs: list = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0, 0.0])  # 畸变系数

    # 相机硬件设置
    enable_hardware_reset: bool = True  # 启动时是否执行硬件复位
    frame_timeout: int = 5000  # 帧等待超时时间（毫秒）


# ==================== 标定板配置 ====================

@dataclass
class CharucoBoardConfig:
    """ChArUco 标定板配置"""
    # ArUco 字典类型
    aruco_dict_type: int = cv2.aruco.DICT_4X4_50  # ArUco 字典类型

    # 标定板尺寸
    rows: int = 5  # 棋盘格行数
    cols: int = 7  # 棋盘格列数

    # 物理尺寸（单位：米）
    square_size: float = 0.025  # 棋盘格方格边长（米）
    marker_size: float = 0.018  # ArUco 二维码边长（米）

    # 检测参数
    min_corners_for_pose: int = 4  # 位姿估计所需的最小角点数

    def validate(self):
        """验证配置参数"""
        assert self.marker_size < self.square_size, \
            f"marker_size ({self.marker_size}) 必须小于 square_size ({self.square_size})"
        assert 0.5 < self.marker_size / self.square_size < 0.9, \
            f"marker_size/square_size 比例应在 0.5-0.9 之间，当前为 {self.marker_size / self.square_size:.2f}"
        assert self.rows >= 3 and self.cols >= 3, \
            f"标定板尺寸至少为 3x3，当前为 {self.rows}x{self.cols}"


# ==================== 数据采集配置 ====================

@dataclass
class DataCollectionConfig:
    """数据采集配置"""
    # 采集数量
    min_samples: int = 15  # 最少采集样本数
    recommended_samples: int = 20  # 推荐采集样本数

    # 位姿变化阈值
    min_position_change: float = 0.02  # 最小位置变化（米），2cm
    min_rotation_change: float = 0.1  # 最小旋转变化（旋转矩阵 Frobenius 范数）

    # 显示参数
    window_name: str = "Data Collection - RealSense D405"  # 窗口名称
    font_face: int = cv2.FONT_HERSHEY_SIMPLEX  # 字体
    font_scale: float = 1.0  # 字体大小
    font_thickness: int = 2  # 字体粗细
    text_color_info: tuple = (0, 255, 0)  # 信息文本颜色（绿色）
    text_color_warning: tuple = (0, 165, 255)  # 警告文本颜色（橙色）

    # 交互提示
    capture_key: str = 's'  # 捕获键
    quit_key: str = 'q'  # 退出键


# ==================== 标定算法配置 ====================

@dataclass
class CalibrationSolverConfig:
    """标定算法配置"""
    # 标定类型
    calibration_type: str = "eye_in_hand"  # "eye_in_hand" 或 "eye_to_hand"

    # 手眼标定方法
    method: int = cv2.CALIB_HAND_EYE_TSAI  # 标定方法（TSAI, PARK, HORAUD, ANDREFF, DANIILIDIS）

    # 位姿验证阈值
    max_identical_poses: int = 2  # 允许的最大相同位姿数量
    pose_similarity_threshold: float = 1e-6  # 位姿相似度阈值

    # ChArUco 检测参数
    use_refine_strategy: bool = True  # 是否使用角点精细化策略


# ==================== 验证和质量评估配置 ====================

@dataclass
class ValidationConfig:
    """验证和质量评估配置"""
    # 重投影误差阈值（像素）
    excellent_threshold: float = 1.0  # 优秀
    good_threshold: float = 2.0  # 良好
    acceptable_threshold: float = 5.0  # 可接受

    # 可视化参数
    reprojection_point_color: tuple = (0, 0, 255)  # 重投影点颜色（红色）
    reprojection_point_radius: int = 8  # 重投影点半径
    detected_corner_color: tuple = (0, 255, 0)  # 检测角点颜色（绿色）
    line_thickness: int = 2  # 线条粗细


# ==================== 数据存储配置 ====================

@dataclass
class StorageConfig:
    """数据存储配置"""
    # 目录路径
    data_dir: str = "calibration_data"  # 数据根目录
    images_subdir: str = "images"  # 图像子目录

    # 文件名
    poses_filename: str = "hand_eye_robot_poses.npy"  # 机械臂位姿文件
    result_filename: str = "hand_eye_result.json"  # 标定结果文件
    result_matrix_filename: str = "T_end_to_cam.npy"  # 变换矩阵文件
    metadata_filename: str = "metadata.json"  # 元数据文件
    error_stats_filename: str = "calibration_error_stats.json"  # 误差统计文件

    # 图像文件格式
    image_format: str = "png"  # 图像格式
    image_prefix: str = "sample_"  # 图像文件前缀

# ==================== 主配置类 ====================

class CalibrationConfig:
    """
    手眼标定主配置类
    整合所有子配置，提供统一的配置接口
    """

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置

        Args:
            config_file: 配置文件路径（可选，支持 JSON 或 YAML）
        """
        # 初始化各子配置
        self.robot = RobotConfig()
        self.camera = CameraConfig()
        self.charuco_board = CharucoBoardConfig()
        self.data_collection = DataCollectionConfig()
        self.calibration_solver = CalibrationSolverConfig()
        self.validation = ValidationConfig()
        self.storage = StorageConfig()

        # 从配置文件加载（如果提供）
        if config_file:
            self.load_from_file(config_file)

        # 验证配置
        self.validate()

        # 初始化路径
        self._init_paths()

    def _init_paths(self):
        """初始化文件路径"""
        self.data_dir = Path(self.storage.data_dir)
        self.images_dir = self.data_dir / self.storage.images_subdir
        self.poses_file = self.data_dir / self.storage.poses_filename
        self.result_file = self.data_dir / self.storage.result_filename
        self.result_matrix_file = self.data_dir / self.storage.result_matrix_filename
        self.metadata_file = self.data_dir / self.storage.metadata_filename
        self.error_stats_file = self.data_dir / self.storage.error_stats_filename

        # 创建目录
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def validate(self):
        """验证所有配置参数"""
        # 验证标定板配置
        self.charuco_board.validate()

        # 验证相机配置
        assert self.camera.width > 0 and self.camera.height > 0, "相机分辨率必须大于 0"
        assert self.camera.fps > 0, "帧率必须大于 0"

        # 验证数据采集配置
        assert self.data_collection.min_samples >= 3, "最少采集样本数必须 >= 3"
        assert self.data_collection.min_position_change > 0, "位置变化阈值必须 > 0"

        # 验证机器人配置
        assert self.robot.arm_side in ["left", "right"], \
            f"arm_side 必须是 'left' 或 'right'，当前为 '{self.robot.arm_side}'"

    def load_from_file(self, config_file: str):
        """
        从配置文件加载配置

        Args:
            config_file: 配置文件路径（JSON 或 YAML）
        """
        config_path = Path(config_file)
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")

        # 根据文件扩展名选择加载方式
        if config_path.suffix in ['.yaml', '.yml']:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
        elif config_path.suffix == '.json':
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path.suffix}")

        # 更新配置
        self._update_from_dict(config_dict)

    def _update_from_dict(self, config_dict: Dict[str, Any]):
        """从字典更新配置"""
        for section, values in config_dict.items():
            if hasattr(self, section) and isinstance(values, dict):
                config_obj = getattr(self, section)
                for key, value in values.items():
                    if hasattr(config_obj, key):
                        setattr(config_obj, key, value)

    def save_to_file(self, config_file: str):
        """
        保存配置到文件

        Args:
            config_file: 配置文件路径（JSON 或 YAML）
        """
        config_dict = self.to_dict()
        config_path = Path(config_file)

        if config_path.suffix in ['.yaml', '.yml']:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
        elif config_path.suffix == '.json':
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
        else:
            raise ValueError(f"不支持的配置文件格式: {config_path.suffix}")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'robot': self.robot.__dict__,
            'camera': self.camera.__dict__,
            'charuco_board': self.charuco_board.__dict__,
            'data_collection': self.data_collection.__dict__,
            'calibration_solver': self.calibration_solver.__dict__,
            'validation': self.validation.__dict__,
            'storage': self.storage.__dict__,
        }

    # ==================== 辅助方法 ====================

    def get_charuco_board(self):
        """
        创建 ChArUco 标定板对象

        Returns:
            cv2.aruco.CharucoBoard: ChArUco 标定板对象
        """
        aruco_dict = cv2.aruco.getPredefinedDictionary(self.charuco_board.aruco_dict_type)
        board = cv2.aruco.CharucoBoard(
            (self.charuco_board.cols, self.charuco_board.rows),
            self.charuco_board.square_size,
            self.charuco_board.marker_size,
            aruco_dict
        )
        return board

    def get_camera_intrinsics(self):
        """
        获取相机内参

        Returns:
            tuple: (camera_matrix, dist_coeffs)
        """
        if self.camera.use_auto_intrinsics:
            return self._get_camera_intrinsics_from_realsense()
        else:
            return self._get_manual_camera_intrinsics()

    def _get_manual_camera_intrinsics(self):
        """获取手动配置的相机内参"""
        camera_matrix = np.array([
            [self.camera.fx, 0, self.camera.cx],
            [0, self.camera.fy, self.camera.cy],
            [0, 0, 1]
        ], dtype=np.float64)

        dist_coeffs = np.array(self.camera.distortion_coeffs, dtype=np.float64)

        return camera_matrix, dist_coeffs

    def _get_camera_intrinsics_from_realsense(self):
        """从 RealSense 相机读取内参"""
        try:
            import pyrealsense2 as rs

            pipeline = rs.pipeline()
            config = rs.config()
            config.enable_stream(
                rs.stream.color,
                self.camera.width,
                self.camera.height,
                rs.format.bgr8,
                self.camera.fps
            )

            profile = pipeline.start(config)
            color_stream = profile.get_stream(rs.stream.color)
            intrinsics = color_stream.as_video_stream_profile().get_intrinsics()

            camera_matrix = np.array([
                [intrinsics.fx, 0, intrinsics.ppx],
                [0, intrinsics.fy, intrinsics.ppy],
                [0, 0, 1]
            ], dtype=np.float64)

            dist_coeffs = np.array(intrinsics.coeffs, dtype=np.float64)

            pipeline.stop()

            print(f"✓ 从 RealSense 相机读取内参成功")
            print(f"  Camera Matrix:\n{camera_matrix}")
            print(f"  Distortion Coeffs: {dist_coeffs}")

            return camera_matrix, dist_coeffs

        except ImportError:
            print("⚠️ 未安装 pyrealsense2，使用手动配置的内参")
            return self._get_manual_camera_intrinsics()
        except Exception as e:
            print(f"⚠️ 从 RealSense 读取内参失败: {e}")
            print("   使用手动配置的内参")
            return self._get_manual_camera_intrinsics()

    def get_sdk_path(self, project_root: Optional[Path] = None) -> Path:
        """
        获取 SDK 路径

        Args:
            project_root: 项目根目录（可选）

        Returns:
            Path: SDK 路径
        """
        if project_root is None:
            # 尝试从当前文件位置推断项目根目录
            project_root = Path(__file__).parent.parent

        # 首先尝试相对路径
        sdk_path = project_root / self.robot.sdk_relative_path
        if sdk_path.exists():
            return sdk_path

        # 尝试搜索路径列表
        for search_path in self.robot.sdk_search_paths:
            if Path(search_path).is_absolute():
                sdk_path = Path(search_path)
            else:
                sdk_path = project_root / search_path

            if sdk_path.exists():
                return sdk_path

        raise FileNotFoundError(
            f"无法找到 SDK 路径。尝试的路径:\n" +
            f"  - {project_root / self.robot.sdk_relative_path}\n" +
            "\n".join(f"  - {p}" for p in self.robot.sdk_search_paths)
        )

    def print_config(self):
        """打印当前配置"""
        print("\n" + "=" * 60)
        print("Eye-in-Hand Calibration Configuration")
        print("=" * 60)

        print(f"\n【机器人配置】")
        print(f"  IP: {self.robot.tcp_host}")
        print(f"  机械臂: {self.robot.arm_side}")
        print(f"  运动速度: {self.robot.move_speed} m/s")
        print(f"  加速度: {self.robot.move_accel} m/s²")

        print(f"\n【相机配置】")
        print(f"  类型: {self.camera.camera_type}")
        print(f"  分辨率: {self.camera.width}x{self.camera.height} @ {self.camera.fps}fps")
        print(f"  自动内参: {self.camera.use_auto_intrinsics}")

        print(f"\n【标定板配置】")
        print(f"  字典类型: {self.charuco_board.aruco_dict_type}")
        print(f"  尺寸: {self.charuco_board.rows} x {self.charuco_board.cols}")
        print(f"  方格大小: {self.charuco_board.square_size * 1000:.1f} mm")
        print(f"  标记大小: {self.charuco_board.marker_size * 1000:.1f} mm")

        print(f"\n【数据采集配置】")
        print(f"  最少样本数: {self.data_collection.min_samples}")
        print(f"  位置变化阈值: {self.data_collection.min_position_change * 1000:.1f} mm")
        print(f"  旋转变化阈值: {self.data_collection.min_rotation_change:.3f}")

        print(f"\n【标定算法配置】")
        print(f"  方法: {self.calibration_solver.method}")

        print(f"\n【验证配置】")
        print(f"  优秀阈值: < {self.validation.excellent_threshold:.1f} 像素")
        print(f"  良好阈值: < {self.validation.good_threshold:.1f} 像素")
        print(f"  可接受阈值: < {self.validation.acceptable_threshold:.1f} 像素")

        print(f"\n【存储配置】")
        print(f"  数据目录: {self.data_dir}")
        print(f"  图像目录: {self.images_dir}")

        print("=" * 60 + "\n")


# ==================== 配置文件模板生成 ====================

def generate_config_template(output_file: str = "calibration_config_template.yaml"):
    """
    生成配置文件模板

    Args:
        output_file: 输出文件路径
    """
    config = CalibrationConfig()
    config.save_to_file(output_file)
    print(f"✓ 配置文件模板已生成: {output_file}")


# ==================== 测试代码 ====================

if __name__ == "__main__":
    # 测试配置
    print("测试默认配置:")
    config = CalibrationConfig()
    config.print_config()

    # 测试 ChArUco 板创建
    board = config.get_charuco_board()
    print(f"✓ ChArUco Board 创建成功")

    # 测试相机内参读取
    camera_matrix, dist_coeffs = config.get_camera_intrinsics()
    print(f"✓ 相机内参读取成功")

    # 生成配置文件模板
    print("\n生成配置文件模板:")
    generate_config_template("calibration_config_template.yaml")
    generate_config_template("calibration_config_template.json")
