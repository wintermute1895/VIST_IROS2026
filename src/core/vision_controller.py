#!/usr/bin/env python3
"""
============================================================================
基于视觉的手部控制器（带状态机）
============================================================================
功能：MediaPipe手部追踪 + 几何特征提取 + 状态机
架构：摄像头帧 → MediaPipe → 捏合比率 → 状态机 → 关节角度

状态机：
- IDLE（空闲）：手完全张开 (ratio > 0.8)
- PRE_GRASP（预抓取）：预抓取姿态 (0.3 < ratio <= 0.8)
- GRASP（抓取）：捏合/抓取姿态 (ratio <= 0.2)

防抖动：需要连续5帧检测到相同状态才会切换
============================================================================
"""

import numpy as np
import cv2
import logging
import os
from typing import List, Tuple, Optional
from enum import Enum
from PIL import Image, ImageDraw, ImageFont


def draw_chinese_text(img: np.ndarray,
                     text: str,
                     position: Tuple[int, int],
                     color: Tuple[int, int, int],
                     size: int = 20) -> np.ndarray:
    """
    使用 PIL 在 OpenCV 图像上绘制中文文本

    参数：
        img: OpenCV 图像 (BGR 格式)
        text: 要绘制的文本（支持中文）
        position: 文本位置 (x, y)
        color: 文本颜色 (B, G, R) - OpenCV 格式
        size: 字体大小

    返回：
        绘制了文本的图像
    """
    # 将 OpenCV 图像 (BGR) 转换为 PIL 图像 (RGB)
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 尝试加载中文字体
    font = None
    chinese_font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "C:\\Windows\\Fonts\\msyh.ttc",  # Windows
    ]

    for font_path in chinese_font_paths:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, size)
                break
            except Exception:
                continue

    # 如果找不到中文字体，使用默认字体并打印警告
    if font is None:
        try:
            font = ImageFont.load_default()
            # 只在第一次警告
            if not hasattr(draw_chinese_text, '_warned'):
                import logging
                logging.warning("未找到中文字体，使用默认字体。中文可能无法正确显示。")
                draw_chinese_text._warned = True
        except Exception:
            font = None

    # 将 OpenCV 的 BGR 颜色转换为 RGB
    color_rgb = (color[2], color[1], color[0])

    # 绘制文本
    draw.text(position, text, font=font, fill=color_rgb)

    # 转换回 OpenCV 图像 (BGR)
    img_bgr = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    return img_bgr


class HandState(Enum):
    """手部状态枚举"""
    IDLE = "IDLE"           # 完全张开
    PRE_GRASP = "PRE_GRASP" # 预抓取姿态
    GRASP = "GRASP"         # 捏合/抓取姿态


class VisionController:
    """
    基于视觉的手部控制器（带状态机）

    处理流程：
    1. MediaPipe手部检测
    2. 几何特征提取（捏合比率）
    3. 带防抖的状态机
    4. 输出目标关节角度
    """

    # ========================================================================
    # 预设关节角度（10自由度）- 测试后请修改这些数值
    # ========================================================================
    # 关节顺序：[拇指俯仰, 拇指偏航, 食指俯仰, 中指俯仰,
    #           无名指俯仰, 小指俯仰, 食指侧摆, 无名指侧摆,
    #           小指侧摆, 拇指侧摆]
    # 单位：度（将直接发送给LinkerHandDriver）
    # ========================================================================

    # IDLE状态：手完全张开
    JOINT_ANGLES_IDLE: List[float] = [
        255.0,  # [0] 拇指俯仰 (Thumb_Pitch)
        255.0,  # [1] 拇指偏航 (Thumb_Yaw)
        255.0,  # [2] 食指俯仰 (Index_Pitch)
        255.0,  # [3] 中指俯仰 (Middle_Pitch)
        255.0,  # [4] 无名指俯仰 (Ring_Pitch)
        255.0,  # [5] 小指俯仰 (Pinky_Pitch)
        255.0,  # [6] 食指侧摆 (Index_Roll)
        255.0,  # [7] 无名指侧摆 (Ring_Roll)
        255.0,  # [8] 小指侧摆 (Pinky_Roll)
        255.0,  # [9] 拇指侧摆 (Thumb_Roll)
    ]

    # PRE_GRASP状态：预抓取姿态（部分闭合）
    JOINT_ANGLES_PRE_GRASP: List[float] = [
        135.0,  # [0] 拇指俯仰 - 待填入：测试后的数值
        50.0,  # [1] 拇指偏航 - 待填入：测试后的数值
        140.0,  # [2] 食指俯仰 - 待填入：测试后的数值
        136.0,  # [3] 中指俯仰 - 待填入：测试后的数值
        255.0,  # [4] 无名指俯仰 - 待填入：测试后的数值
        255.0,  # [5] 小指俯仰 - 待填入：测试后的数值
        184.0,  # [6] 食指侧摆 - 待填入：测试后的数值
        0.0,  # [7] 无名指侧摆 - 待填入：测试后的数值
        0.0,  # [8] 小指侧摆 - 待填入：测试后的数值
        219.0,  # [9] 拇指侧摆 - 待填入：测试后的数值
    ]

    # GRASP状态：完全捏合/抓取（完全闭合）
    JOINT_ANGLES_GRASP: List[float] = [
        118.0,  # [0] 拇指俯仰 - 待填入：测试后的数值
        50.0,  # [1] 拇指偏航 - 待填入：测试后的数值
        127.0,  # [2] 食指俯仰 - 待填入：测试后的数值
        121.0,  # [3] 中指俯仰 - 待填入：测试后的数值
        255.0,  # [4] 无名指俯仰 - 待填入：测试后的数值
        255.0,  # [5] 小指俯仰 - 待填入：测试后的数值
        184.0,  # [6] 食指侧摆 - 待填入：测试后的数值
        0.0,  # [7] 无名指侧摆 - 待填入：测试后的数值
        0.0,  # [8] 小指侧摆 - 待填入：测试后的数值
        219.0,  # [9] 拇指侧摆 - 待填入：测试后的数值
    ]

    # ========================================================================
    # 状态机参数
    # ========================================================================
    RATIO_THRESHOLD_IDLE = 0.8      # ratio > 0.8 → IDLE（空闲）
    RATIO_THRESHOLD_GRASP = 0.2     # ratio <= 0.2 → GRASP（抓取）
    # 0.2 < ratio <= 0.8 → PRE_GRASP（预抓取）

    DEBOUNCE_FRAMES = 5  # 状态切换前需要连续5帧

    def __init__(self,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        """
        初始化视觉控制器

        参数：
            min_detection_confidence: MediaPipe检测置信度阈值
            min_tracking_confidence: MediaPipe追踪置信度阈值
        """
        self.logger = logging.getLogger(__name__)

        # 初始化MediaPipe
        self._init_mediapipe(min_detection_confidence, min_tracking_confidence)

        # 状态机
        self.current_state = HandState.IDLE
        self.candidate_state = HandState.IDLE
        self.debounce_counter = 0

        # 追踪信息
        self.last_pinch_ratio: Optional[float] = None
        self.last_hand_landmarks = None  # 保存最后检测到的手部关键点
        self.frame_count = 0
        self.state_change_count = 0

        # 强制IDLE冷却机制
        self.force_idle_frames = 0  # 剩余强制IDLE帧数
        self.FORCE_IDLE_DURATION = 30  # 强制IDLE持续30帧

        self.logger.info("=" * 70)
        self.logger.info("✅ 视觉控制器初始化完成")
        self.logger.info(f"  防抖帧数: {self.DEBOUNCE_FRAMES}")
        self.logger.info(f"  IDLE阈值: > {self.RATIO_THRESHOLD_IDLE}")
        self.logger.info(f"  GRASP阈值: <= {self.RATIO_THRESHOLD_GRASP}")
        self.logger.info("=" * 70)

    def _init_mediapipe(self,
                       min_detection_confidence: float,
                       min_tracking_confidence: float):
        """初始化MediaPipe手部追踪（使用新API 0.10.x）"""
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            import os
            import urllib.request

            self.mp = mp

            # 下载模型文件（如果不存在）
            model_path = os.path.expanduser('~/.cache/mediapipe/hand_landmarker.task')
            os.makedirs(os.path.dirname(model_path), exist_ok=True)

            if not os.path.exists(model_path):
                self.logger.info("正在下载MediaPipe手部模型...")
                model_url = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
                urllib.request.urlretrieve(model_url, model_path)
                self.logger.info("模型下载完成")

            # 创建HandLandmarker选项
            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.HandLandmarkerOptions(
                base_options=base_options,
                running_mode=vision.RunningMode.VIDEO,
                num_hands=1,
                min_hand_detection_confidence=min_detection_confidence,
                min_hand_presence_confidence=min_tracking_confidence,
                min_tracking_confidence=min_tracking_confidence
            )

            # 创建HandLandmarker
            self.hand_landmarker = vision.HandLandmarker.create_from_options(options)

            # 保存时间戳（用于VIDEO模式）
            self.frame_timestamp_ms = 0

            # 定义手部连接（用于绘制）
            self.HAND_CONNECTIONS = [
                (0, 1), (1, 2), (2, 3), (3, 4),  # 拇指
                (0, 5), (5, 6), (6, 7), (7, 8),  # 食指
                (0, 9), (9, 10), (10, 11), (11, 12),  # 中指
                (0, 13), (13, 14), (14, 15), (15, 16),  # 无名指
                (0, 17), (17, 18), (18, 19), (19, 20),  # 小指
                (5, 9), (9, 13), (13, 17)  # 手掌
            ]

            self.logger.info("✅ MediaPipe初始化完成（新API 0.10.x）")

        except ImportError as e:
            self.logger.error(f"❌ MediaPipe未安装或版本不兼容: {e}")
            self.logger.error("安装命令: pip install mediapipe>=0.10.0")
            raise
        except Exception as e:
            self.logger.error(f"❌ MediaPipe初始化失败: {e}")
            raise

    def _calculate_pinch_ratio(self, landmarks: np.ndarray) -> float:
        """
        计算归一化的捏合比率

        公式：pinch_ratio = 拇指指尖到食指指尖的距离 / 手腕到中指根部的距离

        MediaPipe关键点索引：
        - 0: 手腕 (WRIST)
        - 4: 拇指指尖 (THUMB_TIP)
        - 8: 食指指尖 (INDEX_FINGER_TIP)
        - 9: 中指根部 (MIDDLE_FINGER_MCP)

        参数：
            landmarks: MediaPipe关键点数组 (21 x 3)

        返回：
            归一化的捏合比率 (0.0 到 ~1.5)
        """
        # 提取关键点
        wrist = landmarks[0]              # 手腕
        thumb_tip = landmarks[4]          # 拇指指尖
        index_tip = landmarks[8]          # 食指指尖
        middle_mcp = landmarks[9]         # 中指根部

        # 计算距离（3D欧氏距离）
        pinch_distance = np.linalg.norm(thumb_tip - index_tip)
        hand_size = np.linalg.norm(middle_mcp - wrist)

        # 避免除零
        if hand_size < 1e-6:
            return 1.0

        # 归一化比率
        ratio = pinch_distance / hand_size

        return ratio

    def _determine_state_from_ratio(self, ratio: float) -> HandState:
        """
        根据捏合比率判断手部状态

        参数：
            ratio: 捏合比率值

        返回：
            对应的HandState
        """
        if ratio > self.RATIO_THRESHOLD_IDLE:
            return HandState.IDLE
        elif ratio <= self.RATIO_THRESHOLD_GRASP:
            return HandState.GRASP
        else:
            return HandState.PRE_GRASP

    def _update_state_machine(self, new_state: HandState):
        """
        更新状态机（带防抖）

        参数：
            new_state: 新检测到的状态
        """
        if new_state == self.candidate_state:
            # 相同候选状态，计数器加1
            self.debounce_counter += 1

            # 检查是否达到防抖阈值
            if self.debounce_counter >= self.DEBOUNCE_FRAMES:
                if new_state != self.current_state:
                    # 状态切换确认
                    old_state = self.current_state
                    self.current_state = new_state
                    self.state_change_count += 1

                    self.logger.info(
                        f"🔄 状态切换: {old_state.value} → {new_state.value} "
                        f"(第{self.frame_count}帧)"
                    )
        else:
            # 不同的候选状态，重置计数器
            self.candidate_state = new_state
            self.debounce_counter = 1

    def _get_joint_angles_for_state(self, state: HandState) -> List[float]:
        """
        获取给定状态的目标关节角度

        参数：
            state: 当前手部状态

        返回：
            10个关节角度的列表（单位：度）
        """
        if state == HandState.IDLE:
            return self.JOINT_ANGLES_IDLE.copy()
        elif state == HandState.PRE_GRASP:
            return self.JOINT_ANGLES_PRE_GRASP.copy()
        elif state == HandState.GRASP:
            return self.JOINT_ANGLES_GRASP.copy()
        else:
            # 默认返回IDLE
            return self.JOINT_ANGLES_IDLE.copy()

    def reset_state(self):
        """
        强制重置状态到IDLE（完全张开）

        用于手动重置，会：
        1. 强制设置当前状态为IDLE
        2. 重置防抖计数器
        3. 启动冷却时间，在接下来的N帧内忽略识别结果，强制保持IDLE
        """
        self.logger.info("🔄 强制重置状态到IDLE（完全张开）")

        # 强制设置状态
        self.current_state = HandState.IDLE
        self.candidate_state = HandState.IDLE
        self.debounce_counter = 0

        # 启动强制IDLE冷却时间
        self.force_idle_frames = self.FORCE_IDLE_DURATION

        self.logger.info(f"✅ 状态已重置，将在接下来的{self.FORCE_IDLE_DURATION}帧内保持IDLE状态")

    def process_frame(self, frame: np.ndarray) -> Tuple[List[float], bool, Optional[float]]:
        """
        处理单帧图像并返回目标关节角度

        参数：
            frame: 来自摄像头的BGR图像（OpenCV格式）

        返回：
            元组包含：
            - target_angles: 10个关节角度的列表（单位：度）
            - hand_detected: 是否检测到手
            - pinch_ratio: 当前捏合比率（未检测到手时为None）
        """
        self.frame_count += 1

        # 将BGR转换为RGB供MediaPipe使用
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 转换为MediaPipe Image格式
        mp_image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=frame_rgb)

        # 使用MediaPipe处理（VIDEO模式需要时间戳）
        self.frame_timestamp_ms += 33  # 假设30fps，每帧约33ms
        results = self.hand_landmarker.detect_for_video(mp_image, self.frame_timestamp_ms)

        if results.hand_landmarks and len(results.hand_landmarks) > 0:
            # 检测到手
            hand_landmarks = results.hand_landmarks[0]

            # 保存关键点用于可视化
            self.last_hand_landmarks = hand_landmarks

            # 提取关键点为numpy数组
            landmarks = np.array([
                [lm.x, lm.y, lm.z]
                for lm in hand_landmarks
            ])

            # 计算捏合比率
            pinch_ratio = self._calculate_pinch_ratio(landmarks)
            self.last_pinch_ratio = pinch_ratio

            # 检查是否在强制IDLE冷却期间
            if self.force_idle_frames > 0:
                # 冷却期间，忽略识别结果，强制保持IDLE状态
                self.force_idle_frames -= 1
                self.current_state = HandState.IDLE
                self.candidate_state = HandState.IDLE
                self.debounce_counter = 0

                if self.force_idle_frames == 0:
                    self.logger.info("✅ 强制IDLE冷却期结束，恢复正常状态识别")
            else:
                # 正常状态识别
                # 根据比率判断状态
                detected_state = self._determine_state_from_ratio(pinch_ratio)

                # 更新状态机（带防抖）
                self._update_state_machine(detected_state)

            # 获取当前状态的目标关节角度
            target_angles = self._get_joint_angles_for_state(self.current_state)

            return target_angles, True, pinch_ratio

        else:
            # 未检测到手 - 保持当前状态
            target_angles = self._get_joint_angles_for_state(self.current_state)
            return target_angles, False, None

    def draw_visualization(self,
                          frame: np.ndarray,
                          hand_detected: bool,
                          pinch_ratio: Optional[float]) -> np.ndarray:
        """
        在图像上绘制可视化信息

        参数：
            frame: 来自摄像头的BGR图像
            hand_detected: 是否检测到手
            pinch_ratio: 当前捏合比率

        返回：
            带有可视化叠加层的图像
        """
        # 绘制手部关键点（使用保存的关键点）
        if hand_detected and self.last_hand_landmarks is not None:
            h, w = frame.shape[:2]

            # 绘制关键点
            for landmark in self.last_hand_landmarks:
                x = int(landmark.x * w)
                y = int(landmark.y * h)
                cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)

            # 绘制连接线
            for connection in self.HAND_CONNECTIONS:
                start_idx, end_idx = connection
                start = self.last_hand_landmarks[start_idx]
                end = self.last_hand_landmarks[end_idx]

                start_point = (int(start.x * w), int(start.y * h))
                end_point = (int(end.x * w), int(end.y * h))

                cv2.line(frame, start_point, end_point, (255, 255, 255), 2)

        # 绘制状态文本
        h, w = frame.shape[:2]

        # 手部检测状态 - 使用中文绘制
        if hand_detected:
            status_text = "检测到手部"
            status_color = (0, 255, 0)  # 绿色
        else:
            status_text = "未检测到手"
            status_color = (0, 0, 255)  # 红色

        frame = draw_chinese_text(frame, status_text, (10, 10),
                                 status_color, size=32)

        # 当前状态 - 使用中文绘制
        state_text = f"状态: {self.current_state.value}"
        state_color = {
            HandState.IDLE: (255, 255, 0),      # 青色
            HandState.PRE_GRASP: (0, 255, 255), # 黄色
            HandState.GRASP: (0, 165, 255)      # 橙色
        }.get(self.current_state, (255, 255, 255))

        frame = draw_chinese_text(frame, state_text, (10, 50),
                                 state_color, size=32)

        # 捏合比率 - 使用中文绘制
        if pinch_ratio is not None:
            ratio_text = f"捏合比率: {pinch_ratio:.3f}"
            frame = draw_chinese_text(frame, ratio_text, (10, 90),
                                     (255, 255, 255), size=28)

        # 防抖计数器（如果正在转换）- 使用中文绘制
        if self.candidate_state != self.current_state:
            debounce_text = f"防抖: {self.debounce_counter}/{self.DEBOUNCE_FRAMES}"
            frame = draw_chinese_text(frame, debounce_text, (10, 130),
                                     (255, 200, 0), size=24)

        return frame

    def get_status(self) -> dict:
        """
        获取控制器状态

        返回：
            包含状态信息的字典
        """
        return {
            'current_state': self.current_state.value,
            'candidate_state': self.candidate_state.value,
            'debounce_counter': self.debounce_counter,
            'last_pinch_ratio': self.last_pinch_ratio,
            'frame_count': self.frame_count,
            'state_change_count': self.state_change_count,
        }

    def close(self):
        """关闭MediaPipe资源"""
        if hasattr(self, 'hands'):
            self.hands.close()
        self.logger.info("✅ 视觉控制器已关闭")
