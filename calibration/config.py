"""
手眼标定配置中心
================
所有可配置参数的集中管理。
修改此文件以适配不同的机器人、相机和标定板。
"""

from typing import Literal, Dict, Any
from pathlib import Path
import cv2
import numpy as np

# =============================================================================
# 标定模式
# =============================================================================
# 'eye_in_hand': 相机安装在机械臂末端，标定板固定在桌面
#                目标：求解 T_flange_to_camera（手眼矩阵）
# 'eye_to_hand': 相机固定在头顶，标定板安装在机械臂末端
#                目标：求解 T_base_to_camera（眼到手矩阵）
CALIBRATION_MODE: Literal['eye_in_hand', 'eye_to_hand'] = 'eye_in_hand'

# =============================================================================
# 机器人位姿格式配置（标定精度的关键）
# =============================================================================
# 此配置允许系统适配不同机器人制造商的位姿输出格式，无需修改核心代码。
#
# 重要提示：不同机器人制造商使用不同的约定：
# - Universal Robots (UR): 轴角表示（rotvec），位置在前
# - ABB: 四元数 (w,x,y,z)，位置在前
# - KUKA: 欧拉角 ABC（ZYX 外旋），位置在前
# - Franka Emika: 列主序 4x4 矩阵
# - LinkerArm (LBot): 欧拉角 XYZ 内旋，弧度，位置在前
#
# 修改此字典以匹配您的机器人输出格式。

ROBOT_POSE_FMT: Dict[str, Any] = {
    # -------------------------------------------------------------------------
    # 旋转表示类型
    # -------------------------------------------------------------------------
    # 'euler': 欧拉角 (roll, pitch, yaw)
    # 'quat': 四元数 (x, y, z, w) 或 (w, x, y, z)
    # 'rotvec': 旋转向量（轴角表示）
    # 'matrix': 已经是 4x4 齐次变换矩阵
    'type': 'euler',

    # -------------------------------------------------------------------------
    # 角度单位（仅适用于 'euler' 和 'rotvec' 类型）
    # -------------------------------------------------------------------------
    # 'rad': 弧度
    # 'deg': 角度
    'unit': 'rad',

    # -------------------------------------------------------------------------
    # 欧拉角序列（仅适用于 'euler' 类型）
    # -------------------------------------------------------------------------
    # 内旋（旋转坐标系）: 'xyz', 'xzy', 'yxz', 'yzx', 'zxy', 'zyx'
    # 外旋（固定坐标系）: 'XYZ', 'XZY', 'YXZ', 'YZX', 'ZXY', 'ZYX'
    #
    # 常见约定：
    # - 'xyz' (内旋): Roll-Pitch-Yaw，许多机器人使用（LinkerArm, UR）
    # - 'ZYX' (外旋): 等价于 'xyz' 内旋，航空航天领域使用
    # - 'zyx' (内旋): Yaw-Pitch-Roll
    'seq': 'xyz',

    # -------------------------------------------------------------------------
    # 四元数格式（仅适用于 'quat' 类型）
    # -------------------------------------------------------------------------
    # 'xyzw': 四元数为 [x, y, z, w]（scipy, ROS 约定）
    # 'wxyz': 四元数为 [w, x, y, z]（某些机器人库）
    'quat_format': 'xyzw',

    # -------------------------------------------------------------------------
    # 位姿数组顺序
    # -------------------------------------------------------------------------
    # True: [x, y, z, rx, ry, rz] - 位置在前（最常见）
    # False: [rx, ry, rz, x, y, z] - 旋转在前（罕见）
    'is_position_first': True,

    # -------------------------------------------------------------------------
    # 位置单位
    # -------------------------------------------------------------------------
    # 'm': 米（标定的标准单位）
    # 'mm': 毫米（某些工业机器人）
    'position_unit': 'm',
}

# =============================================================================
# 标定板类型配置
# =============================================================================
# 'charuco': ChArUco 标定板（多角点，精度高）
# 'single_marker': 单个 ArUco 标记（4角点，适合贴在机械手上）
MARKER_TYPE: Literal['charuco', 'single_marker'] = 'charuco'

# =============================================================================
# CHARUCO 标定板配置
# =============================================================================
# ⚠️ 关键：使用卡尺或精密测量工具测量这些值！
# 不正确的测量会导致标定结果不准确。

CHARUCO_CONFIG: Dict[str, Any] = {
    # ArUco 字典类型
    # 选项: cv2.aruco.DICT_4X4_50, DICT_5X5_50, DICT_6X6_50, DICT_7X7_50 等
    'dict_type': cv2.aruco.DICT_4X4_50,

    # 标定板尺寸（方格数量）
    'board_rows': 5,  # Y 方向的方格数
    'board_cols': 7,  # X 方向的方格数

    # 物理尺寸（单位：米）
    # ⚠️ 用卡尺仔细测量！
    'square_size': 0.025,  # 每个方格的边长（例如 40mm = 0.040m）
    'marker_size': 0.018  # ArUco 标记的边长（例如 30mm = 0.030m）

    # 注意：marker_size 应该 < square_size，通常为 square_size 的 0.75 倍
}

# =============================================================================
# 单个 ARUCO/APRILTAG 标记配置
# =============================================================================
# 用于 Eye-to-Hand 标定，标记贴在机械手背上

SINGLE_MARKER_CONFIG: Dict[str, Any] = {
    # 标记字典类型
    # ArUco 选项: cv2.aruco.DICT_4X4_50, DICT_5X5_50, DICT_6X6_50, DICT_7X7_50
    # AprilTag 选项: cv2.aruco.DICT_APRILTAG_16h5, DICT_APRILTAG_25h9,
    #               DICT_APRILTAG_36h10, DICT_APRILTAG_36h11
    'dict_type': cv2.aruco.DICT_APRILTAG_36h11,

    # 标记 ID（使用哪个标记）
    'marker_id': 0,

    # 标记物理尺寸（单位：米）
    # ⚠️ 建议至少 50mm 以上，用卡尺仔细测量！
    # 注意：测量的是黑色方块的外边长（不包括白边）
    'marker_size': 0.050,  # 例如 50mm = 0.050m
}

# =============================================================================
# 相机配置
# =============================================================================
CAMERA_CONFIG: Dict[str, Any] = {
    # 相机类型
    # 'realsense': Intel RealSense 相机（D405, D435i 等）
    # 'opencv': 通用 USB 相机（通过 OpenCV）
    'type': 'realsense',

    # RealSense 特定设置
    'realsense': {
        'width': 640,
        'height': 480,
        'fps': 30,
        'use_intrinsics': True,  # 从相机自动加载内参
    },

    # 手动相机内参（当 use_intrinsics=False 或相机不可用时使用）
    # 格式: [[fx, 0, cx], [0, fy, cy], [0, 0, 1]]
    'manual_intrinsics': {
        'camera_matrix': np.array([
            [615.0, 0.0, 320.0],
            [0.0, 615.0, 240.0],
            [0.0, 0.0, 1.0]
        ], dtype=np.float64),
        'dist_coeffs': np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64),
    },
}

# =============================================================================
# 数据采集配置
# =============================================================================
DATA_COLLECTION_CONFIG: Dict[str, Any] = {
    # 采集模式
    # 'manual': 手动模式，按 's' 键拍照
    # 'auto': 自动模式，定时拍照
    'mode': 'auto',

    # 自动模式的拍照间隔（秒）
    'auto_interval': 10.0,
}

# =============================================================================
# 数据路径
# =============================================================================
DATA_DIR = Path("calibration_data")
PATHS: Dict[str, Path] = {
    'data_dir': DATA_DIR,
    'images_dir': DATA_DIR / "images",
    'poses_file': DATA_DIR / "robot_poses.npy",
    'result_file': DATA_DIR / "calibration_result.json",
    'result_matrix_file': DATA_DIR / "hand_eye_matrix.npy",
}

# 创建目录
for path in [PATHS['data_dir'], PATHS['images_dir']]:
    path.mkdir(parents=True, exist_ok=True)

# =============================================================================
# 标定算法参数
# =============================================================================
CALIBRATION_PARAMS: Dict[str, Any] = {
    # 手眼标定方法
    # 选项: cv2.CALIB_HAND_EYE_TSAI, CALIB_HAND_EYE_PARK,
    #       CALIB_HAND_EYE_HORAUD, CALIB_HAND_EYE_ANDREFF,
    #       CALIB_HAND_EYE_DANIILIDIS
    'method': cv2.CALIB_HAND_EYE_TSAI,

    # 所需的最少有效位姿对数
    'min_samples': 10,

    # 角点检测参数
    'corner_refinement': True,  # 使用亚像素优化
    'corner_win_size': (5, 5),  # 角点优化窗口大小
}

# =============================================================================
# 仿真参数（用于无硬件的软件验证）
# =============================================================================
SIMULATION_CONFIG: Dict[str, Any] = {
    # 生成的合成位姿数量
    'num_poses': 20,

    # Ground Truth 变换（用于验证）
    # 这是我们将尝试恢复的"真实"手眼矩阵
    # 格式: 4x4 齐次变换矩阵
    #
    # 简化测试：只有平移，没有旋转（相机和法兰坐标系对齐）
    'ground_truth_eye_in_hand': np.array([
        [1.0, 0.0, 0.0, 0.05],   # 相机 X = 法兰 X，X 方向偏移 50mm
        [0.0, 1.0, 0.0, 0.02],   # 相机 Y = 法兰 Y，Y 方向偏移 20mm
        [0.0, 0.0, 1.0, 0.08],   # 相机 Z = 法兰 Z，Z 方向偏移 80mm
        [0.0, 0.0, 0.0, 1.0]
    ], dtype=np.float64),

    'ground_truth_eye_to_hand': np.array([
        [1.0, 0.0, 0.0, 0.5],     # 相机距基座 X 方向 500mm
        [0.0, 1.0, 0.0, 0.3],     # 相机距基座 Y 方向 300mm
        [0.0, 0.0, 1.0, 0.8],     # 相机距基座 Z 方向 800mm（头顶）
        [0.0, 0.0, 0.0, 1.0]
    ], dtype=np.float64),

    # 噪声参数（模拟真实世界的测量误差）
    'pixel_noise_std': 0.5,           # 像素噪声标准差
    'pose_noise_translation': 0.0001, # 0.1mm 平移噪声
    'pose_noise_rotation': 0.001,     # ~0.057 度旋转噪声
}

# =============================================================================
# 辅助函数
# =============================================================================

def get_charuco_board():
    """
    从配置创建 ChArUco 标定板对象。

    Returns:
        cv2.aruco.CharucoBoard: ChArUco 标定板对象
    """
    aruco_dict = cv2.aruco.getPredefinedDictionary(CHARUCO_CONFIG['dict_type'])
    board = cv2.aruco.CharucoBoard(
        (CHARUCO_CONFIG['board_cols'], CHARUCO_CONFIG['board_rows']),
        CHARUCO_CONFIG['square_size'],
        CHARUCO_CONFIG['marker_size'],
        aruco_dict
    )
    return board

def print_config():
    """打印当前配置摘要。"""
    print("\n" + "="*70)
    print("手眼标定系统配置")
    print("="*70)
    print(f"标定模式: {CALIBRATION_MODE.upper()}")
    print(f"\n机器人位姿格式:")
    print(f"  类型: {ROBOT_POSE_FMT['type']}")
    print(f"  单位: {ROBOT_POSE_FMT['unit']}")
    if ROBOT_POSE_FMT['type'] == 'euler':
        print(f"  序列: {ROBOT_POSE_FMT['seq']}")
    print(f"  位置在前: {ROBOT_POSE_FMT['is_position_first']}")
    print(f"\nChArUco 标定板:")
    print(f"  尺寸: {CHARUCO_CONFIG['board_rows']} x {CHARUCO_CONFIG['board_cols']}")
    print(f"  方格: {CHARUCO_CONFIG['square_size']*1000:.1f} mm")
    print(f"  标记: {CHARUCO_CONFIG['marker_size']*1000:.1f} mm")
    print(f"\n数据目录: {PATHS['data_dir']}")
    print("="*70 + "\n")

if __name__ == "__main__":
    print_config()
