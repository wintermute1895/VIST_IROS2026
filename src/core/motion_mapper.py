"""
Three-Vector Motion Mapping for Human-to-Robot Teleoperation

This module implements the core mapping algorithm that converts MediaPipe-detected
human keypoints (shoulder, elbow, wrist, index_mcp, pinky_mcp) into robot end-effector poses.

Mathematical Foundation:
- Vector Extraction: Computes upper arm and forearm direction vectors
- Coordinate Alignment: Transforms from shoulder frame to robot base frame
- Position Mapping: Scales human motion to robot arm dimensions
- Orientation Mapping: Uses knuckle vector (index→pinky) to avoid singularity when arm is straight

Key Innovation: Using knuckle vector instead of palm vector eliminates singularity
when the arm is fully extended (high-frequency motion in teleoperation).

Reference: VIST (Vision-based Intent-aware State Teleoperation), IROS 2026
"""

import numpy as np
from scipy.spatial.transform import Rotation
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import get_config


class ArmMotionMapper:
    """
    Maps human arm pose to robot end-effector target pose using Three-Vector Mapping.

    Coordinate Systems:
    - Camera Frame: MediaPipe output (right-handed, typically Y-down)
    - Robot Base Frame: Robot coordinate system (right-handed, Z-up)

    Design Principle: Stateless mapping (no internal filtering)
    """

    def __init__(self, robot_shoulder_pos=None, arm_lengths=None):
        """
        Initialize motion mapper with robot arm parameters.

        参数可以从配置文件自动加载，也可以手动指定（手动指定优先）

        Args:
            robot_shoulder_pos: Robot shoulder position in base frame [x, y, z] (可选，默认从配置文件读取)
            arm_lengths: Dictionary with keys 'upper' and 'forearm' (可选，默认从配置文件读取)
                        Example: {'upper': 0.30, 'forearm': 0.25}
        """
        print("🗺️  [ArmMotionMapper] 初始化运动映射器...")

        # 加载配置
        config = get_config()

        # 使用配置文件参数（如果未手动指定）
        if robot_shoulder_pos is None:
            robot_shoulder_pos = config.robot_shoulder_position
        if arm_lengths is None:
            arm_lengths = config.robot_arm_lengths

        # Robot parameters
        self.P_base_shoulder = np.array(robot_shoulder_pos, dtype=np.float64)
        self.L_upper = arm_lengths['upper']
        self.L_fore = arm_lengths.get('forearm', arm_lengths.get('fore'))  # 兼容两种命名

        # 坐标转换矩阵（从配置文件读取）
        # Vision Frame (Shoulder Frame): X=up, Y=right, Z=forward
        # Robot Base Frame (body_base_link): X=forward, Y=left, Z=up
        # 转换矩阵定义在 config/system_config.yaml
        self.R_vision_to_robot = config.rotation_matrix

        # 滤波参数（从配置文件读取）
        self.alpha = config.filter_alpha

        # 初始化滤波状态
        self.prev_pos = None  # Previous position for EMA filtering
        self.prev_rot = None  # Previous rotation (quaternion) for SLERP

        print(f"✅ [ArmMotionMapper] 初始化完成")
        print(f"   上臂长度: {self.L_upper:.3f}m")
        print(f"   前臂长度: {self.L_fore:.3f}m")
        print(f"   肩部位置: {self.P_base_shoulder}")
        print(f"   滤波系数: {self.alpha}")

    def set_filter_alpha(self, alpha):
        """
        Set the smoothing coefficient for EMA filtering.

        Args:
            alpha: Smoothing coefficient (0.0 to 1.0)
                  - 0.0: Maximum smoothing (output = previous output)
                  - 1.0: No smoothing (output = current input)
                  - Typical values: 0.1-0.5
        """
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"Alpha must be in [0, 1], got {alpha}")
        self.alpha = alpha
        print(f"✅ [ArmMotionMapper] Filter alpha set to {alpha}")

    def human_to_robot(self, human_kps):
        """
        Map human arm keypoints to robot end-effector pose using Three-Vector Mapping.

        ⚠️ IMPORTANT: Expects input data in SHOULDER FRAME, relative to shoulder origin!
        VisionNode performs:
        1. Dynamic zeroing (shoulder at [0,0,0])
        2. Depth fusion (RealSense + MediaPipe)

        This method performs:
        1. Coordinate transformation (Shoulder Frame → Robot Base Frame)
        2. Position mapping (human arm → robot arm)
        3. Orientation calculation (three-vector method)

        Args:
            human_kps: Dictionary with keys:
                      - 'shoulder': numpy array [0, 0, 0] (origin, in shoulder frame)
                      - 'elbow': numpy array [x, y, z] (relative to shoulder, in shoulder frame)
                      - 'wrist': numpy array [x, y, z] (relative to shoulder, in shoulder frame)
                      - 'index_mcp': numpy array [x, y, z] - index finger (in shoulder frame)
                      - 'pinky_mcp': numpy array [x, y, z] - pinky finger (in shoulder frame)

        Returns:
            tuple: (target_pos, target_quat, debug_info)
                - target_pos: 3D position [x, y, z] (numpy array, in robot base frame)
                - target_quat: Quaternion [x, y, z, w] (numpy array)
                - debug_info: Dictionary with intermediate results for debugging

            Returns None if input is invalid (singular configuration)

        Raises:
            ValueError: If keypoints are missing
        """
        # ==========================================
        # Step 1: Vector Extraction
        # ==========================================
        try:
            P_S = np.array(human_kps['shoulder'], dtype=np.float64)
            P_E = np.array(human_kps['elbow'], dtype=np.float64)
            P_W = np.array(human_kps['wrist'], dtype=np.float64)
            P_index = np.array(human_kps['index_mcp'], dtype=np.float64)
            P_pinky = np.array(human_kps['pinky_mcp'], dtype=np.float64)
        except KeyError as e:
            raise ValueError(f"Missing keypoint: {e}")

        # Compute arm vectors (in shoulder frame, relative to shoulder)
        # Since shoulder is at origin [0,0,0], these ARE the direction vectors
        V_upper = P_E - P_S  # Upper arm vector (shoulder → elbow)
        V_fore = P_W - P_E   # Forearm vector (elbow → wrist)
        V_knuckle = P_index - P_pinky  # Knuckle vector (pinky → index, 横向参考向量)

        # ==========================================
        # Step 2: Safety Check (Singularity Detection)
        # ==========================================
        # Threshold: 1mm to avoid numerical instability
        SINGULARITY_THRESHOLD = 0.001

        norm_upper = np.linalg.norm(V_upper)
        norm_fore = np.linalg.norm(V_fore)
        norm_knuckle = np.linalg.norm(V_knuckle)

        if norm_upper < SINGULARITY_THRESHOLD:
            print(f"⚠️ [Mapper] Singularity: Upper arm vector too small ({norm_upper*1000:.2f}mm)")
            return None
        if norm_fore < SINGULARITY_THRESHOLD:
            print(f"⚠️ [Mapper] Singularity: Forearm vector too small ({norm_fore*1000:.2f}mm)")
            return None
        if norm_knuckle < SINGULARITY_THRESHOLD:
            print(f"⚠️ [Mapper] Singularity: Knuckle vector too small ({norm_knuckle*1000:.2f}mm)")
            return None

        # ==========================================
        # ==========================================
        # Step 3: Coordinate Transformation (Shoulder Frame → Robot Base Frame)
        # ==========================================
        # Input (Shoulder Frame from VisionNode):
        #   X = up, Y = right, Z = forward
        # Output (Robot Base Frame):
        #   X = forward, Y = left, Z = up
        #
        # Transformation matrix from config: R_vision_to_robot @ vector
        V_upper_robot = self.R_vision_to_robot @ V_upper
        V_fore_robot = self.R_vision_to_robot @ V_fore
        V_knuckle_robot = self.R_vision_to_robot @ V_knuckle

        # ==========================================
        # Step 4: Position Mapping
        # ==========================================
        # Normalize direction vectors
        d_upper = V_upper_robot / np.linalg.norm(V_upper_robot)
        d_fore = V_fore_robot / np.linalg.norm(V_fore_robot)

        # Compute robot joint positions using arm lengths
        T_elbow = self.P_base_shoulder + d_upper * self.L_upper
        T_wrist = T_elbow + d_fore * self.L_fore

        # ==========================================
        # Step 5: Orientation Mapping (Using Knuckle Vector)
        # ==========================================
        # Key Innovation: Use knuckle vector (index→pinky) instead of palm vector
        # This avoids singularity when arm is fully extended (high-frequency motion)

        # Z-axis: Along forearm direction (approach/forward direction)
        Z_axis = d_fore  # Already normalized

        # Y-axis: Compute from knuckle vector (hand back normal direction)
        # Y_temp = Z × V_knuckle (cross product gives perpendicular vector)
        # This represents the normal to the palm plane
        Y_temp = np.cross(Z_axis, V_knuckle_robot)
        Y_temp_norm = np.linalg.norm(Y_temp)

        # Handle degenerate case: knuckle vector parallel to forearm (extremely rare)
        if Y_temp_norm < SINGULARITY_THRESHOLD:
            print(f"⚠️ [Mapper] Singularity: Knuckle parallel to forearm (rare), using fallback")
            # Choose arbitrary perpendicular vector
            if abs(Z_axis[2]) < 0.9:
                Y_temp = np.cross(Z_axis, np.array([0, 0, 1]))
            else:
                Y_temp = np.cross(Z_axis, np.array([1, 0, 0]))
            Y_temp_norm = np.linalg.norm(Y_temp)

        # CRITICAL: Normalize Y_temp to get unit Y_axis
        Y_axis = Y_temp / Y_temp_norm

        # X-axis: Cross product of two unit vectors (automatically unit length)
        # X = Y × Z (ensures right-handed coordinate system)
        X_axis = np.cross(Y_axis, Z_axis)

        # Construct rotation matrix [X, Y, Z] as columns
        # This ensures: R @ [1,0,0] = X, R @ [0,1,0] = Y, R @ [0,0,1] = Z
        R_target = np.column_stack([X_axis, Y_axis, Z_axis])

        # Verify orthogonality (for debugging)
        # R^T @ R should be identity for orthogonal matrix
        orthogonality_error = np.linalg.norm(R_target.T @ R_target - np.eye(3))
        if orthogonality_error > 1e-6:
            print(f"⚠️ [Mapper] Warning: Rotation matrix not orthogonal (error={orthogonality_error:.2e})")

        # Convert to quaternion [x, y, z, w]
        rot_obj = Rotation.from_matrix(R_target)
        target_quat = rot_obj.as_quat()  # Returns [x, y, z, w]

        # ==========================================
        # Step 6: Apply EMA Filtering (Smoothing)
        # ==========================================
        curr_pos = T_wrist.copy()
        curr_quat = target_quat.copy()

        if self.prev_pos is not None and self.prev_rot is not None:
            # Position filtering: Exponential Moving Average (EMA)
            filtered_pos = self.alpha * curr_pos + (1.0 - self.alpha) * self.prev_pos

            # Rotation filtering: Spherical Linear Interpolation (SLERP)
            from scipy.spatial.transform import Slerp

            # Create Rotation objects from quaternions
            rot_prev = Rotation.from_quat(self.prev_rot)
            rot_curr = Rotation.from_quat(curr_quat)

            # SLERP interpolation: t=alpha means blend from prev to curr
            # We want: output = (1-alpha)*prev + alpha*curr
            # So we use t=alpha
            key_times = [0, 1]
            key_rots = Rotation.concatenate([rot_prev, rot_curr])
            slerp = Slerp(key_times, key_rots)
            filtered_rot_obj = slerp(self.alpha)
            filtered_quat = filtered_rot_obj.as_quat()
        else:
            # First frame: no filtering
            filtered_pos = curr_pos
            filtered_quat = curr_quat

        # Update previous values for next iteration
        self.prev_pos = filtered_pos.copy()
        self.prev_rot = filtered_quat.copy()

        # ==========================================
        # Step 7: Debug Information
        # ==========================================
        debug_info = {
            'elbow_pos': T_elbow,
            'wrist_pos': T_wrist,
            'upper_arm_vector': V_upper_robot,
            'forearm_vector': V_fore_robot,
            'knuckle_vector': V_knuckle_robot,
            'rotation_matrix': R_target,
            'orthogonality_error': orthogonality_error,
            'x_axis': X_axis,
            'y_axis': Y_axis,
            'z_axis': Z_axis,
            'filtered_pos': filtered_pos,
            'filtered_quat': filtered_quat,
            'unfiltered_pos': curr_pos,
            'unfiltered_quat': curr_quat
        }

        return filtered_pos, filtered_quat, debug_info
