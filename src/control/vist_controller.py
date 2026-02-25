"""
VIST 控制器
封装 VIST 算法逻辑（纯算法，不涉及硬件）

更新日期：2026-02-23
新增功能：
- 意图检测与冲突检测（EnhancedIntentDetector）
- 安全控制（SafeRobotController）
- 目标检测（AprilTag/ArUco）
- 5 阶段状态机控制流程
- 统一日志系统
"""

import numpy as np
import pinocchio as pin
from pathlib import Path

from src.core.motion_mapper import ArmMotionMapper
from src.core.ik_solver import PinocchioIKSolver
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.geometric_arm_solver import GeometricArmSolver
from src.control.safe_robot_controller import SafeRobotController

# 新增：意图检测
from src.core.intent_detector import (
    EnhancedIntentDetector,
    IntentFactors,
    compute_human_command,
    compute_algorithm_expectation
)
from src.perception.target_detector import create_target_detector

# 日志系统
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class VISTController:
    """VIST 算法控制器（纯算法逻辑）

    支持两种模式：
    1. 基础模式：直接运动映射 + IK 求解（向后兼容）
    2. 增强模式：意图检测 + 冲突检测 + 状态机控制（新功能）

    通过配置选项 enable_intent_detection 切换模式
    """

    def __init__(self, config):
        """
        初始化 VIST 控制器

        Args:
            config: VISTConfig 配置对象
        """
        self.config = config

        # 检查是否启用增强功能
        self.enable_intent_detection = getattr(config, 'enable_intent_detection', False)
        self.enable_target_detection = getattr(config, 'enable_target_detection', False)

        # 1. 初始化运动映射器
        logger.info("初始化运动映射器...")
        self.mapper = ArmMotionMapper(
            robot_shoulder_pos=config.robot_shoulder_position,
            arm_lengths=config.robot_arm_lengths,
        )
        logger.info("运动映射器初始化完成")

        # 2. 初始化 IK 求解器
        logger.info("初始化 IK 求解器...")
        project_root = Path(__file__).parent.parent.parent
        urdf_path = project_root / "config" / config.robot_model_urdf_file

        self.ik_solver = PinocchioIKSolver(
            urdf_path=str(urdf_path),
            end_effector_frame=config.robot_model_end_effector_frame
        )
        logger.info("IK 求解器初始化完成")

        # 3. 初始化 VIST 框架
        logger.info("初始化 VIST 框架...")

        # 3.1 初始化几何求解器
        geometric_solver = None
        if config.vist_geometric_solver_enabled:
            logger.info("启用几何解析求解器...")
            geometric_solver = GeometricArmSolver(
                model=self.ik_solver.model,
                data=self.ik_solver.data,
                controlled_joints=self.ik_solver.controlled_indices,
                ee_frame_id=self.ik_solver.ee_frame_id,
                config=config
            )
            logger.info(f"几何求解器初始化完成 (trust_weight={config.vist_geometric_solver_trust_weight})")

        # 3.2 初始化 VIST 卡尔曼滤波器
        self.vist_filter = VISTKalmanFilter(
            self.ik_solver,
            config,
            geometric_solver=geometric_solver
        )
        logger.info("VIST Kalman Filter 初始化完成")

        # 4. 初始化安全控制器
        logger.info("初始化安全控制器...")
        self.safety_controller = SafeRobotController(
            config=config,
            enable_logging=True
        )
        logger.info("安全控制器初始化完成")

        # 5. 初始化增强功能（如果启用）
        self.intent_detector = None
        self.target_detector = None
        self.target_socket_pos = None
        self.coord_transform = None  # 坐标变换管理器

        # 6. 初始化坐标变换管理器
        logger.info("初始化坐标变换管理器...")
        try:
            from src.perception.coordinate_transform_manager import CoordinateTransformManager
            self.coord_transform = CoordinateTransformManager(config=config)
            logger.info("坐标变换管理器初始化完成")
        except Exception as e:
            logger.warning(f"坐标变换管理器初始化失败: {e}")
            logger.warning("将在无标定模式下运行（需要手动提供基座坐标系下的目标位置）")

        if self.enable_intent_detection:
            logger.info("初始化意图检测器（增强模式）...")
            self.intent_detector = EnhancedIntentDetector(config)
            logger.info("意图检测器初始化完成")

        if self.enable_target_detection:
            logger.info("初始化目标检测器...")
            detector_type = getattr(config, 'target_detector_type', 'apriltag')
            self.target_detector = create_target_detector(detector_type, config)
            logger.info(f"目标检测器初始化完成 (类型: {detector_type})")

        # 初始化状态
        self.q_current = pin.neutral(self.ik_solver.model).copy()
        self.current_pos = np.zeros(3)
        self.current_velocity = np.zeros(3)

        # 打印模式信息
        mode = "增强模式（意图检测 + 冲突检测）" if self.enable_intent_detection else "基础模式（直接控制）"
        logger.info(f"VIST 控制器初始化完成 - {mode}")


    def process(self, human_keypoints, camera_image=None):
        """
        处理人体关键点，计算安全的关节角度

        Args:
            human_keypoints: 人体关键点字典
            camera_image: 相机图像（用于目标检测，可选）

        Returns:
            (q_safe, success, debug_info)
            - q_safe: 安全的关节角度 (7-DoF)
            - success: 是否成功
            - debug_info: 调试信息字典
        """
        # 根据模式选择处理方法
        if self.enable_intent_detection:
            return self._process_enhanced(human_keypoints, camera_image)
        else:
            return self._process_basic(human_keypoints)

    def _process_basic(self, human_keypoints):
        """
        基础模式处理（向后兼容）

        直接运动映射 + IK 求解，无意图检测
        """
        debug_info = {}

        # 1. 运动映射
        result = self.mapper.human_to_robot(human_keypoints)
        if result is None:
            return None, False, {"error": "运动映射失败"}

        target_pos, target_quat, mapper_debug = result
        target_elbow = mapper_debug['elbow_pos']
        debug_info['target_pos'] = target_pos
        debug_info['target_elbow'] = target_elbow
        debug_info['mode'] = 'basic'

        # 添加肘部角度调试信息
        if 'vector_angle' in mapper_debug:
            debug_info['vector_angle'] = mapper_debug['vector_angle']
            debug_info['elbow_angle_human'] = mapper_debug['elbow_angle_human']
            debug_info['elbow_angle_motor'] = mapper_debug['elbow_angle_motor']

        # 2. 工作空间检查
        shoulder_pos = self.config.robot_shoulder_position
        dist_to_shoulder = np.linalg.norm(target_pos - shoulder_pos)
        max_reach = self.config.robot_arm_lengths['upper'] + \
                    self.config.robot_arm_lengths['forearm']

        if dist_to_shoulder > max_reach * 0.98:
            logger.error(f"目标位置超出工作空间: {dist_to_shoulder:.3f}m > {max_reach*0.98:.3f}m")
            return None, False, {"error": f"目标位置超出工作空间 ({dist_to_shoulder:.3f}m > {max_reach*0.98:.3f}m)"}

        # 3. VIST 卡尔曼滤波求解
        q_solution, success, error = self.vist_filter.solve(
            target_pos=target_pos,
            target_quat=target_quat,
            q_init=self.q_current,
            elbow_pos=target_elbow,
            shoulder_pos=shoulder_pos
        )

        if not success:
            return None, False, {"error": f"VIST 求解失败 (误差={error*1000:.2f}mm)"}

        debug_info['ik_error'] = error

        # 4. 安全控制器检查（⚠️ 已禁用，改为在主循环中调用）
        # 原因：在VISTController内部调用SafeRobotController会导致速度估计问题
        # 解决方案：像仿真一样，在主循环中调用SafeRobotController
        # q_dot_estimated = self._get_velocity_estimate()
        # q_safe, safety_status = self.safety_controller.process_command(q_solution, q_dot_estimated)
        # debug_info['safety_status'] = safety_status
        # debug_info['velocity_estimation_method'] = getattr(self.config, 'velocity_estimation_method', 'kalman')

        # if safety_status['emergency_stop']:
        #     return None, False, {"error": "紧急停止激活"}

        # 直接返回q_solution，安全检查在主循环中进行
        q_safe = q_solution
        debug_info['safety_status'] = {
            'emergency_stop': False,
            'velocity_limited': False,
            'acceleration_limited': False,
            'position_limited': False
        }

        # 5. 更新状态
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(q_safe) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_safe[i]
        self.q_current = q_full

        return q_safe, True, debug_info

    def _process_enhanced(self, human_keypoints, camera_image=None):
        """
        增强模式处理（新功能）

        包含意图检测、冲突检测、状态机控制
        """
        debug_info = {}
        debug_info['mode'] = 'enhanced'

        # 1. 目标检测（如果启用且有图像）
        if self.enable_target_detection and camera_image is not None and self.target_socket_pos is None:
            target_result = self.target_detector.detect(camera_image)
            if target_result is not None:
                self.target_socket_pos = target_result.position
                logger.info(f"检测到目标位置: {self.target_socket_pos}")
                debug_info['target_detected'] = True

        # 2. 运动映射
        result = self.mapper.human_to_robot(human_keypoints)
        if result is None:
            return None, False, {"error": "运动映射失败"}

        human_target_pos, human_target_quat, mapper_debug = result
        target_elbow = mapper_debug['elbow_pos']
        debug_info['human_target_pos'] = human_target_pos

        # 3. 计算人类指令和算法期望
        human_command = compute_human_command(
            self.current_pos,
            human_target_pos,
            self.current_velocity
        )

        algorithm_expectation = np.zeros(3)
        if self.target_socket_pos is not None:
            algorithm_expectation = compute_algorithm_expectation(
                self.current_pos,
                self.target_socket_pos,
                virtual_fixture_gain=1.0
            )

        # 4. 意图检测（带冲突检测）
        distance = np.linalg.norm(self.target_socket_pos - self.current_pos) if self.target_socket_pos is not None else 1.0
        velocity = np.linalg.norm(self.current_velocity)
        alignment_error = distance  # 简化：使用距离作为对齐误差

        intent_result = self.intent_detector.detect_intent(
            distance=distance,
            velocity=velocity,
            human_command=human_command,
            algorithm_expectation=algorithm_expectation,
            alignment_error=alignment_error,
            current_depth=0.0  # TODO: 从传感器获取插入深度
        )

        debug_info['intent_state'] = intent_result.state.value
        debug_info['alpha'] = intent_result.alpha
        debug_info['beta'] = intent_result.beta
        debug_info['alpha_effective'] = intent_result.alpha_effective

        # 5. 根据状态生成目标位置
        target_pos, target_quat = self._generate_target_from_intent(
            intent_result,
            human_target_pos,
            human_target_quat,
            self.target_socket_pos
        )

        debug_info['target_pos'] = target_pos

        # 6. VIST 卡尔曼滤波求解
        shoulder_pos = self.config.robot_shoulder_position
        q_solution, success, error = self.vist_filter.solve(
            target_pos=target_pos,
            target_quat=target_quat,
            q_init=self.q_current,
            elbow_pos=target_elbow,
            shoulder_pos=shoulder_pos,
            alpha=intent_result.alpha_effective  # 使用有效意图因子
        )

        if not success:
            return None, False, {"error": f"VIST 求解失败 (误差={error*1000:.2f}mm)"}

        debug_info['ik_error'] = error

        # 7. 安全控制器检查（⚠️ 已禁用，改为在主循环中调用）
        # 原因：在VISTController内部调用SafeRobotController会导致速度估计问题
        # 解决方案：像仿真一样，在主循环中调用SafeRobotController
        # q_dot_estimated = self._get_velocity_estimate()
        # q_safe, safety_status = self.safety_controller.process_command(q_solution, q_dot_estimated)
        # debug_info['safety_status'] = safety_status
        # debug_info['velocity_estimation_method'] = getattr(self.config, 'velocity_estimation_method', 'kalman')

        # if safety_status['emergency_stop']:
        #     return None, False, {"error": "紧急停止激活"}

        # 直接返回q_solution，安全检查在主循环中进行
        q_safe = q_solution
        debug_info['safety_status'] = {
            'emergency_stop': False,
            'velocity_limited': False,
            'acceleration_limited': False,
            'position_limited': False
        }

        # 8. 更新状态
        q_full = pin.neutral(self.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
            if i < len(q_safe) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_safe[i]
        self.q_current = q_full
        self.current_pos = target_pos  # 更新当前位置（简化）

        return q_safe, True, debug_info

    def _generate_target_from_intent(self, intent_result, human_target_pos, human_target_quat, algorithm_target_pos):
        """
        根据意图检测结果生成目标位置

        Args:
            intent_result: 意图检测结果
            human_target_pos: 人类目标位置
            human_target_quat: 人类目标姿态
            algorithm_target_pos: 算法目标位置

        Returns:
            (target_pos, target_quat): 混合后的目标位置和姿态
        """
        state = intent_result.state
        alpha_eff = intent_result.alpha_effective

        if state == IntentState.APPROACHING:
            # 阶段 1: 人类主导接近
            return human_target_pos, human_target_quat

        elif state == IntentState.VISUAL_ADMITTANCE:
            # 阶段 2: 视觉导纳（算法主导，但允许人类接管）
            if algorithm_target_pos is not None:
                # 线性混合
                target_pos = (1 - alpha_eff) * human_target_pos + alpha_eff * algorithm_target_pos
            else:
                target_pos = human_target_pos
            return target_pos, human_target_quat

        elif state == IntentState.CORRECTION_OVERRIDE:
            # 阶段 3: 修正/接管（人类接管）
            if algorithm_target_pos is not None:
                target_pos = (1 - alpha_eff) * human_target_pos + alpha_eff * algorithm_target_pos
            else:
                target_pos = human_target_pos
            return target_pos, human_target_quat

        elif state == IntentState.CONSTRAINED_INSERTION:
            # 阶段 4: 约束插入（算法主导）
            # TODO: 实现插入速度控制
            if algorithm_target_pos is not None:
                return algorithm_target_pos, human_target_quat
            else:
                return human_target_pos, human_target_quat

        elif state == IntentState.RELEASE:
            # 阶段 5: 释放
            return human_target_pos, human_target_quat

        else:
            return human_target_pos, human_target_quat


    def get_safety_statistics(self):
        """获取安全控制统计信息"""
        return {
            'safety_controller': self.safety_controller.get_statistics()
        }

    def get_intent_state(self):
        """获取当前意图状态"""
        if self.intent_detector is not None:
            return self.intent_detector.current_state
        return None

    def reset(self):
        """重置控制器状态"""
        self.q_current = pin.neutral(self.ik_solver.model).copy()
        self.current_pos = np.zeros(3)
        self.current_velocity = np.zeros(3)
        self.target_socket_pos = None
        self.safety_controller.reset()

        if self.intent_detector is not None:
            self.intent_detector.reset()

        logger.info("VISTController 状态已重置")

    def _get_velocity_estimate(self):
        """
        获取关节速度估计（支持多种方法，用于消融实验）

        Returns:
            q_dot: 估计的关节速度 (7,)，如果不可用则返回None
        """
        method = getattr(self.config, 'velocity_estimation_method', 'kalman')

        if method == 'kalman':
            # 方法1：使用VIST卡尔曼滤波器的速度估计（推荐）
            if hasattr(self, 'vist_filter') and self.vist_filter is not None:
                q_dot = self.vist_filter.state[self.vist_filter.n_joints:self.vist_filter.n_joints*2]
                return q_dot.copy()
            else:
                logger.warning("卡尔曼滤波器不可用，回退到数值微分")
                return None

        elif method == 'numerical':
            # 方法2：使用数值微分（基线方法，用于对比）
            # 返回None，让安全控制器使用数值微分
            return None

        elif method == 'measured':
            # 方法3：使用机器人SDK返回的速度测量值（如果可用）
            # 这需要在真机控制循环中实现
            logger.warning("measured方法需要在真机控制循环中实现")
            return None

        else:
            logger.warning(f"未知的速度估计方法: {method}，使用数值微分")
            return None

