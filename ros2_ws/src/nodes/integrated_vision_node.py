#!/usr/bin/env python3
"""
集成视觉节点（支持多相机、目标检测、意图计算）

功能：
1. 多相机管理（每个相机有不同角色）
2. 手部追踪（MediaPipe）
3. 目标检测（AprilTag）
4. 场景感知意图计算
5. 降级策略

相机角色：
- intent_detection: 用于手部追踪和意图计算
- fine_manipulation: 用于精密操作的目标检测
- workspace_monitoring: 用于工作空间监控
"""

import cv2
import numpy as np
import socket
import json
import time
import yaml
from pathlib import Path
from typing import Dict, Optional, Tuple
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import get_config
from src.perception.apriltag_detector import AprilTagDetector, TargetManager
from src.core.intent_detector import ContinuousIntentDetector, IntentFactors

# MediaPipe
import mediapipe_compat
import mediapipe as mp


class IntegratedVisionNode:
    """集成视觉节点（多相机 + 多功能）"""

    def __init__(self):
        print("🚀 [IntegratedVisionNode] 初始化集成视觉节点...")

        # 加载配置
        self.system_config = get_config()
        self.camera_config = self._load_camera_config()

        # 初始化相机（按角色分组）
        self.cameras = self._init_cameras()

        # 初始化MediaPipe（用于手部追踪）
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # 初始化目标检测器
        if self.camera_config['target_detection']['enable']:
            self.target_detector = AprilTagDetector(
                self.camera_config['target_detection']
            )
            self.target_manager = TargetManager(
                self.camera_config['intent_detection']
            )
        else:
            self.target_detector = None
            self.target_manager = None

        # 初始化意图检测器
        self.intent_detector = ContinuousIntentDetector(self.system_config)

        # UDP发送器
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = (self.system_config.udp_ip, self.system_config.udp_port)

        # 降级策略
        self.fallback_config = self.camera_config.get('fallback_strategy', {})
        self.last_valid_keypoints = None
        self.consecutive_failures = 0

        # 性能监控
        self.fps = 0
        self.frame_count = 0
        self.fps_start_time = time.time()

        print("✅ [IntegratedVisionNode] 初始化完成")
        print(f"   相机数量: {len(self.cameras)}")
        print(f"   目标检测: {'启用' if self.target_detector else '禁用'}")

    def _load_camera_config(self) -> dict:
        """加载相机配置"""
        config_path = Path(__file__).parent.parent.parent / 'config' / 'camera_config.yaml'

        if not config_path.exists():
            print(f"⚠️  配置文件不存在: {config_path}")
            return {}

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _init_cameras(self) -> Dict[str, dict]:
        """
        初始化相机（按角色分组）

        Returns:
            {
                'intent_detection': {pipeline, align, config, ...},
                'fine_manipulation': {...},
                ...
            }
        """
        import pyrealsense2 as rs

        cameras = {}

        for cam_config in self.camera_config.get('cameras', []):
            if not cam_config.get('enabled', True):
                continue

            role = cam_config.get('role', 'unknown')
            camera_id = cam_config['id']

            try:
                # 创建pipeline
                pipeline = rs.pipeline()
                config = rs.config()

                # 如果指定了序列号
                if cam_config['serial'] != 'auto':
                    config.enable_device(cam_config['serial'])

                # 配置流
                streams = cam_config['streams']
                if 'color' in streams:
                    c = streams['color']
                    config.enable_stream(
                        rs.stream.color,
                        c['resolution'][0], c['resolution'][1],
                        rs.format.bgr8, c['fps']
                    )

                if 'depth' in streams:
                    d = streams['depth']
                    config.enable_stream(
                        rs.stream.depth,
                        d['resolution'][0], d['resolution'][1],
                        rs.format.z16, d['fps']
                    )

                # 启动pipeline
                profile = pipeline.start(config)

                # 创建对齐对象
                align = rs.align(rs.stream.color) if 'depth' in streams else None

                # 获取深度比例
                depth_sensor = profile.get_device().first_depth_sensor()
                depth_scale = depth_sensor.get_depth_scale()

                # 存储相机信息
                cameras[role] = {
                    'id': camera_id,
                    'pipeline': pipeline,
                    'align': align,
                    'config': cam_config,
                    'depth_scale': depth_scale,
                    'profile': profile
                }

                print(f"✅ 相机 {camera_id} ({role}) 启动成功")

            except Exception as e:
                print(f"❌ 相机 {camera_id} ({role}) 启动失败: {e}")

        return cameras

    def get_frames(self, role: str) -> Tuple[Optional[np.ndarray], Optional[object], Optional[object]]:
        """
        获取指定角色相机的帧

        Args:
            role: 相机角色 ('intent_detection', 'fine_manipulation', etc.)

        Returns:
            (color_image, color_frame, depth_frame)
        """
        if role not in self.cameras:
            return None, None, None

        camera = self.cameras[role]

        try:
            frames = camera['pipeline'].wait_for_frames(timeout_ms=1000)

            if camera['align']:
                frames = camera['align'].process(frames)

            color_frame = frames.get_color_frame()
            depth_frame = frames.get_depth_frame()

            if not color_frame:
                return None, None, None

            color_image = np.asanyarray(color_frame.get_data())

            return color_image, color_frame, depth_frame

        except Exception as e:
            print(f"⚠️  获取 {role} 相机帧失败: {e}")
            return None, None, None

    def process_hand_tracking(
        self,
        color_image: np.ndarray,
        depth_frame
    ) -> Optional[dict]:
        """
        处理手部追踪（MediaPipe）

        Returns:
            关键点字典或None
        """
        # 翻转图像（镜像模式）
        frame = cv2.flip(color_image, 1)

        # MediaPipe处理
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if not results.pose_world_landmarks:
            # 检测失败，使用降级策略
            return self._handle_detection_failure()

        # 提取关键点
        landmarks = results.pose_world_landmarks.landmark

        # 获取关键点索引
        shoulder_idx = self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value
        elbow_idx = self.mp_pose.PoseLandmark.RIGHT_ELBOW.value
        wrist_idx = self.mp_pose.PoseLandmark.RIGHT_WRIST.value
        index_idx = self.mp_pose.PoseLandmark.RIGHT_INDEX.value
        pinky_idx = self.mp_pose.PoseLandmark.RIGHT_PINKY.value

        # 提取坐标
        shoulder = np.array([landmarks[shoulder_idx].x, landmarks[shoulder_idx].y, landmarks[shoulder_idx].z])
        elbow = np.array([landmarks[elbow_idx].x, landmarks[elbow_idx].y, landmarks[elbow_idx].z])
        wrist = np.array([landmarks[wrist_idx].x, landmarks[wrist_idx].y, landmarks[wrist_idx].z])
        index_mcp = np.array([landmarks[index_idx].x, landmarks[index_idx].y, landmarks[index_idx].z])
        pinky_mcp = np.array([landmarks[pinky_idx].x, landmarks[pinky_idx].y, landmarks[pinky_idx].z])

        # 动态归零（以肩部为原点）
        elbow_rel = elbow - shoulder
        wrist_rel = wrist - shoulder
        index_rel = index_mcp - shoulder
        pinky_rel = pinky_mcp - shoulder

        # 深度融合（如果有深度帧）
        if depth_frame:
            # 获取手腕深度
            h, w = frame.shape[:2]
            wrist_pixel_x = int((1 - landmarks[wrist_idx].x) * w)  # 翻转后的X坐标
            wrist_pixel_y = int(landmarks[wrist_idx].y * h)
            wrist_depth = depth_frame.get_distance(wrist_pixel_x, wrist_pixel_y)

            # 获取肩部深度
            shoulder_pixel_x = int((1 - landmarks[shoulder_idx].x) * w)
            shoulder_pixel_y = int(landmarks[shoulder_idx].y * h)
            shoulder_depth = depth_frame.get_distance(shoulder_pixel_x, shoulder_pixel_y)

            # 计算相对深度
            if wrist_depth > 0 and shoulder_depth > 0:
                rel_depth = wrist_depth - shoulder_depth
                wrist_rel[2] = -rel_depth  # Z轴方向修正

        keypoints = {
            'shoulder': np.array([0, 0, 0]),  # 原点
            'elbow': elbow_rel,
            'wrist': wrist_rel,
            'index_mcp': index_rel,
            'pinky_mcp': pinky_rel
        }

        # 更新降级策略的缓存
        self.last_valid_keypoints = keypoints
        self.consecutive_failures = 0

        return keypoints

    def _handle_detection_failure(self) -> Optional[dict]:
        """处理检测失败（降级策略）"""
        self.consecutive_failures += 1

        strategy = self.fallback_config.get('mediapipe_failure', {}).get('strategy', 'use_last_frame')
        max_failures = self.fallback_config.get('mediapipe_failure', {}).get('max_failure_frames', 5)

        if self.consecutive_failures > max_failures:
            print(f"⚠️  连续失败 {self.consecutive_failures} 帧，超过阈值")
            return None

        if strategy == 'use_last_frame' and self.last_valid_keypoints is not None:
            return self.last_valid_keypoints

        return None

    def process_target_detection(
        self,
        color_frame,
        depth_frame,
        camera_intrinsics
    ) -> Optional[np.ndarray]:
        """
        处理目标检测

        Returns:
            目标位置 [x, y, z] 或 None
        """
        if not self.target_detector:
            return None

        # 检测目标
        targets = self.target_detector.detect(color_frame, depth_frame, camera_intrinsics)

        # 选择目标
        selected_target = self.target_manager.select_target(targets)

        if selected_target:
            return selected_target.position_3d

        return None

    def run(self):
        """主循环"""
        print("🎬 [IntegratedVisionNode] 开始运行...")

        while True:
            loop_start = time.time()

            # 1. 获取手部追踪相机的帧
            color_image, color_frame, depth_frame = self.get_frames('intent_detection')

            if color_image is None:
                print("⚠️  无法获取手部追踪相机帧")
                time.sleep(0.033)
                continue

            # 2. 手部追踪
            keypoints = self.process_hand_tracking(color_image, depth_frame)

            if keypoints is None:
                continue

            # 3. 目标检测（如果启用）
            target_position = None
            if self.target_detector and color_frame and depth_frame:
                intrinsics = color_frame.profile.as_video_stream_profile().intrinsics
                target_position = self.process_target_detection(color_frame, depth_frame, intrinsics)

            # 4. 意图计算
            wrist_pos = keypoints['wrist']
            # 计算速度（简化：使用零速度）
            velocity = np.zeros(3)

            # 如果有目标位置，使用目标位置；否则使用默认偏移
            if target_position is not None:
                intent_target = target_position
            else:
                intent_target = wrist_pos + np.array([0, 0, 0.2])

            intent_factors = self.intent_detector.detect_intent(
                wrist_pos, intent_target, velocity
            )

            # 5. 发送数据
            data = {
                'keypoints': {k: v.tolist() for k, v in keypoints.items()},
                'intent_factor': intent_factors.alpha,
                'target_position': target_position.tolist() if target_position is not None else None,
                'timestamp': time.time()
            }

            try:
                self.sock.sendto(json.dumps(data).encode(), self.udp_addr)
            except Exception as e:
                print(f"⚠️  UDP发送失败: {e}")

            # 6. 可视化（如果启用）
            if self.camera_config.get('debug', {}).get('enable_visualization', False):
                self._visualize(color_image, keypoints, intent_factors, target_position)

            # 7. FPS计算
            self.frame_count += 1
            if time.time() - self.fps_start_time > 1.0:
                self.fps = self.frame_count / (time.time() - self.fps_start_time)
                print(f"📊 FPS: {self.fps:.1f} | Intent α: {intent_factors.alpha:.3f}")
                self.frame_count = 0
                self.fps_start_time = time.time()

            # 8. 控制帧率
            loop_time = time.time() - loop_start
            target_dt = 1.0 / 30.0
            if loop_time < target_dt:
                time.sleep(target_dt - loop_time)

    def _visualize(self, image, keypoints, intent_factors, target_position):
        """可视化"""
        vis = image.copy()

        # 显示意图因子
        text = f"Intent: {intent_factors.alpha:.3f}"
        cv2.putText(vis, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # 显示目标位置
        if target_position is not None:
            text = f"Target: ({target_position[0]:.2f}, {target_position[1]:.2f}, {target_position[2]:.2f})"
            cv2.putText(vis, text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        cv2.imshow('VIST Vision', vis)
        cv2.waitKey(1)

    def cleanup(self):
        """清理资源"""
        for camera in self.cameras.values():
            camera['pipeline'].stop()
        cv2.destroyAllWindows()


def main():
    node = IntegratedVisionNode()

    try:
        node.run()
    except KeyboardInterrupt:
        print("\n🛑 用户中断")
    finally:
        node.cleanup()


if __name__ == '__main__':
    main()
