#!/usr/bin/env python3
"""
MediaPipe兼容层 - 将新API (0.10.x) 包装成旧API (0.8.x) 的接口
"""
import mediapipe as mp
import numpy as np
import os
import urllib.request


class PoseLandmark:
    """模拟旧API的PoseLandmark枚举"""
    LEFT_SHOULDER = type('obj', (object,), {'value': 11})()
    LEFT_ELBOW = type('obj', (object,), {'value': 13})()
    LEFT_WRIST = type('obj', (object,), {'value': 15})()
    LEFT_INDEX = type('obj', (object,), {'value': 19})()
    LEFT_PINKY = type('obj', (object,), {'value': 17})()


class PoseResults:
    """模拟旧API的结果对象"""
    def __init__(self):
        self.pose_landmarks = None
        self.pose_world_landmarks = None


class LandmarkList:
    """模拟旧API的landmark列表"""
    def __init__(self, landmarks):
        self.landmark = landmarks


class Pose:
    """模拟旧API的Pose类，内部使用新API"""

    def __init__(self, static_image_mode=False, model_complexity=1,
                 smooth_landmarks=True, min_detection_confidence=0.5,
                 min_tracking_confidence=0.5):
        """初始化Pose检测器"""

        # 下载模型文件（如果不存在）
        model_path = os.path.join(os.path.dirname(__file__), 'pose_landmarker_lite.task')
        if not os.path.exists(model_path):
            print("📥 [MediaPipe Compat] 下载 Pose Landmarker 模型...")
            model_url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
            try:
                urllib.request.urlretrieve(model_url, model_path)
                print(f"✅ [MediaPipe Compat] 模型已下载")
            except Exception as e:
                print(f"❌ [MediaPipe Compat] 模型下载失败: {e}")
                raise

        # 创建新API的PoseLandmarker
        base_options = mp.tasks.BaseOptions(model_asset_path=model_path)

        # 根据static_image_mode选择运行模式
        running_mode = mp.tasks.vision.RunningMode.IMAGE if static_image_mode else mp.tasks.vision.RunningMode.VIDEO

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=running_mode,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False
        )

        self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)
        self.running_mode = running_mode
        self.frame_timestamp_ms = 0

        print("✅ [MediaPipe Compat] Pose检测器初始化完成")

    def process(self, image):
        """
        处理图像并返回姿态检测结果

        :param image: RGB图像 (numpy array)
        :return: PoseResults对象
        """
        # 创建MediaPipe Image对象
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)

        # 根据运行模式调用不同的检测方法
        if self.running_mode == mp.tasks.vision.RunningMode.IMAGE:
            detection_result = self.landmarker.detect(mp_image)
        else:
            # VIDEO模式需要时间戳
            self.frame_timestamp_ms += 33  # 假设30fps
            detection_result = self.landmarker.detect_for_video(mp_image, self.frame_timestamp_ms)

        # 转换结果为旧API格式
        results = PoseResults()

        if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
            # 转换屏幕坐标landmarks
            results.pose_landmarks = LandmarkList(detection_result.pose_landmarks[0])

            # 转换世界坐标landmarks
            if detection_result.pose_world_landmarks and len(detection_result.pose_world_landmarks) > 0:
                results.pose_world_landmarks = LandmarkList(detection_result.pose_world_landmarks[0])

        return results

    def close(self):
        """关闭检测器"""
        self.landmarker.close()


# 模拟旧API的drawing_utils和drawing_styles
class DrawingUtils:
    """模拟旧API的绘图工具"""

    @staticmethod
    def draw_landmarks(image, landmark_list, connections, landmark_drawing_spec=None):
        """
        在图像上绘制关键点和连接线

        :param image: 图像
        :param landmark_list: landmark列表
        :param connections: 连接关系
        :param landmark_drawing_spec: 绘图规格（忽略）
        """
        import cv2

        if landmark_list is None:
            return

        landmarks = landmark_list.landmark
        h, w, _ = image.shape

        # 绘制关键点
        for landmark in landmarks:
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            cv2.circle(image, (x, y), 3, (0, 255, 0), -1)

        # 绘制连接线（简化版）
        pose_connections = [
            (11, 13), (13, 15), (15, 19), (15, 17),  # 左臂
            (12, 14), (14, 16), (16, 20), (16, 18),  # 右臂
            (11, 12), (11, 23), (12, 24), (23, 24),  # 躯干
        ]

        for start_idx, end_idx in pose_connections:
            if start_idx < len(landmarks) and end_idx < len(landmarks):
                start = landmarks[start_idx]
                end = landmarks[end_idx]
                start_point = (int(start.x * w), int(start.y * h))
                end_point = (int(end.x * w), int(end.y * h))
                cv2.line(image, start_point, end_point, (0, 255, 0), 2)


class DrawingStyles:
    """模拟旧API的绘图样式"""

    @staticmethod
    def get_default_pose_landmarks_style():
        """返回默认姿态关键点样式（实际上被忽略）"""
        return None


# 创建模拟的solutions模块
class Solutions:
    """模拟旧API的solutions模块"""

    class PoseModule:
        """模拟pose子模块"""
        Pose = Pose
        PoseLandmark = PoseLandmark
        POSE_CONNECTIONS = []  # 简化，实际在DrawingUtils中硬编码

    pose = PoseModule()
    drawing_utils = DrawingUtils()
    drawing_styles = DrawingStyles()


# 将兼容层注入到mediapipe模块中
if not hasattr(mp, 'solutions'):
    mp.solutions = Solutions()
    print("✅ [MediaPipe Compat] 兼容层已加载")
