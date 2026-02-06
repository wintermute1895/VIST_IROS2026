#!/usr/bin/env python3
"""
Vision Node with RealSense Depth Integration
使用 MediaPipe Pose 检测姿态 + RealSense 深度数据提高 Z 轴精度

改进点：
1. 使用 RealSense RGB 流（替代普通摄像头）
2. 同时获取深度流，提供真实的 Z 坐标
3. 保持 MediaPipe 的姿态检测能力
4. 自动对齐 RGB 和深度图
"""
import cv2
import mediapipe as mp
import numpy as np
import socket
import json
import time
import pyrealsense2 as rs


class VisionNodeWithDepth:
    def __init__(self, udp_ip="127.0.0.1", udp_port=6001, scale=1.0,
                 width=640, height=480, fps=30):
        """
        初始化视觉节点（带深度）
        :param udp_ip: UDP 目标 IP
        :param udp_port: UDP 目标端口
        :param scale: 缩放因子（调整灵敏度）
        :param width: 图像宽度
        :param height: 图像高度
        :param fps: 帧率
        """
        print("📷 [VisionNodeDepth] 初始化视觉节点 (MediaPipe + RealSense Depth)...")

        # ==========================================
        # 1. 初始化 RealSense
        # ==========================================
        self.pipeline = rs.pipeline()
        self.config = rs.config()

        # 配置 RGB 流
        self.config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        # 配置深度流
        self.config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)

        # 启动 pipeline
        print("🔌 [VisionNodeDepth] 启动 RealSense pipeline...")
        self.profile = self.pipeline.start(self.config)

        # 获取深度传感器的深度比例（用于将深度值转换为米）
        depth_sensor = self.profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        print(f"   深度比例: {self.depth_scale} (深度值 * 比例 = 米)")

        # 创建对齐对象（将深度图对齐到 RGB 图）
        self.align = rs.align(rs.stream.color)

        # 存储图像尺寸
        self.width = width
        self.height = height

        # ==========================================
        # 2. 初始化 MediaPipe Pose
        # ==========================================
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,  # 0=Lite, 1=Full, 2=Heavy
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        # ==========================================
        # 3. 初始化 UDP 发送器
        # ==========================================
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = (udp_ip, udp_port)
        print(f"📡 [VisionNodeDepth] UDP 发送目标: {udp_ip}:{udp_port}")

        # 参数
        self.scale = scale

        # FPS 计算
        self.fps = 0
        self.frame_count = 0
        self.fps_start_time = time.time()

        # 深度统计（用于调试）
        self.depth_stats = {
            'valid_count': 0,
            'invalid_count': 0,
            'avg_depth': 0.0
        }

        print("✅ [VisionNodeDepth] 初始化完成")

    def get_depth_at_pixel(self, depth_frame, x, y, radius=3):
        """
        获取指定像素位置的深度值（带邻域平均）

        :param depth_frame: RealSense 深度帧
        :param x: 像素 X 坐标
        :param y: 像素 Y 坐标
        :param radius: 邻域半径（用于平均，减少噪声）
        :return: 深度值（米），如果无效则返回 None
        """
        # 边界检查
        x = int(np.clip(x, 0, self.width - 1))
        y = int(np.clip(y, 0, self.height - 1))

        # 获取邻域深度值
        depths = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                px = np.clip(x + dx, 0, self.width - 1)
                py = np.clip(y + dy, 0, self.height - 1)
                depth_value = depth_frame.get_distance(px, py)
                if depth_value > 0:  # 有效深度
                    depths.append(depth_value)

        if len(depths) == 0:
            return None

        # 返回中位数（比平均值更鲁棒）
        return np.median(depths)

    def mediapipe_to_robot_coords(self, mp_point, real_depth=None):
        """
        将 MediaPipe 坐标系转换为肩膀坐标系

        ⚠️ 重要：图像在MediaPipe处理前已被翻转（cv2.flip），所以X轴已经镜像！

        MediaPipe Pose World Landmarks (处理翻转后的图像):
        - X: 视频中向左（对应用户物理上的右，因为镜像）
        - Y: 下
        - Z: 向外（背离相机，深度为正）

        肩膀坐标系 (Shoulder Frame):
        - X: 上（垂直方向）
        - Y: 右（水平方向，用户的物理右侧）
        - Z: 前（水平方向，靠近相机的方向）

        转换规则:
        x_shoulder = -y_mp  (向上抬手 → Y减小 → X增大)
        y_shoulder = x_mp   (向右移动 → 视频中向左 → X增大 → Y增大)
        z_shoulder = -rel_depth  (向前伸手 → 靠近相机 → rel_depth减小 → z增大 → Z增大)

        :param mp_point: MediaPipe 世界坐标 [x, y, z]
        :param real_depth: RealSense 真实深度（米），如果提供则替换 Z 坐标
        :return: 肩膀坐标系 [x, y, z]
        """
        x_mp, y_mp, z_mp = mp_point

        # 如果提供了真实深度，使用它替换 MediaPipe 的 Z 坐标
        if real_depth is not None:
            # 关键修正：Z 轴正方向是"靠近相机"
            # real_depth 是相对深度（wrist_depth - shoulder_depth）
            # 向前伸手 → wrist_depth < shoulder_depth → real_depth < 0
            # 但我们希望 Z 增大，所以需要取反
            z_mp = -real_depth
            # 调试输出
            if hasattr(self, '_debug_counter'):
                self._debug_counter += 1
            else:
                self._debug_counter = 0
            if self._debug_counter % 30 == 0:  # 每30帧输出一次
                print(f"[DEBUG] real_depth={real_depth:.4f}, z_mp={z_mp:.4f}, z_final={z_mp * self.scale:.4f}")

        return np.array([
            -y_mp * self.scale,  # MediaPipe -Y(上) → 肩膀 X(上，垂直)
            x_mp * self.scale,   # MediaPipe X(视频左/物理右) → 肩膀 Y(右，水平)
            z_mp * self.scale    # MediaPipe Z(前) → 肩膀 Z(前，水平) [修正：去掉负号]
        ])

    def process_frame(self):
        """
        处理一帧图像 - 实现动态归零机制 + RealSense 深度
        :return: (annotated_frame, keypoints_dict) 或 (None, None) 如果失败
        """
        # ==========================================
        # Step 1: 获取 RealSense 帧
        # ==========================================
        try:
            frames = self.pipeline.wait_for_frames(timeout_ms=1000)
        except RuntimeError as e:
            print(f"⚠️ [VisionNodeDepth] 无法获取 RealSense 帧: {e}")
            return None, None

        # 对齐深度图到 RGB 图
        aligned_frames = self.align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        depth_frame = aligned_frames.get_depth_frame()

        if not color_frame or not depth_frame:
            print("⚠️ [VisionNodeDepth] 无法获取 RGB 或深度帧")
            return None, None

        # 转换为 numpy 数组
        frame = np.asanyarray(color_frame.get_data())

        # ==========================================
        # Step 2: 翻转图像（镜像模式）
        # ==========================================
        frame = cv2.flip(frame, 1)

        # ⚠️ 注意：深度图也需要翻转以保持对齐
        # 但我们不能直接翻转 depth_frame 对象，需要在查询时处理

        # ==========================================
        # Step 3: MediaPipe Pose 处理
        # ==========================================
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        # 初始化关键点字典
        keypoints = None

        if results.pose_world_landmarks and results.pose_landmarks:
            # 获取世界坐标（单位：米）
            landmarks_world = results.pose_world_landmarks.landmark
            landmarks_pixel = results.pose_landmarks.landmark

            # ==========================================
            # 【动态归零】关键步骤
            # ==========================================
            # 1. 获取左肩作为原点（Landmark 11）- 对应物理右臂
            left_shoulder_world = landmarks_world[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]
            left_shoulder_pixel = landmarks_pixel[self.mp_pose.PoseLandmark.LEFT_SHOULDER.value]

            origin_mp = np.array([left_shoulder_world.x, left_shoulder_world.y, left_shoulder_world.z])

            # 2. 获取其他关键点
            left_elbow_world = landmarks_world[self.mp_pose.PoseLandmark.LEFT_ELBOW.value]
            left_wrist_world = landmarks_world[self.mp_pose.PoseLandmark.LEFT_WRIST.value]
            left_index_world = landmarks_world[self.mp_pose.PoseLandmark.LEFT_INDEX.value]
            left_pinky_world = landmarks_world[self.mp_pose.PoseLandmark.LEFT_PINKY.value]

            left_elbow_pixel = landmarks_pixel[self.mp_pose.PoseLandmark.LEFT_ELBOW.value]
            left_wrist_pixel = landmarks_pixel[self.mp_pose.PoseLandmark.LEFT_WRIST.value]
            left_index_pixel = landmarks_pixel[self.mp_pose.PoseLandmark.LEFT_INDEX.value]
            left_pinky_pixel = landmarks_pixel[self.mp_pose.PoseLandmark.LEFT_PINKY.value]

            # ==========================================
            # 【关键改进】使用 RealSense 深度数据
            # ==========================================
            # 获取每个关键点的真实深度
            # ⚠️ 注意：由于图像翻转，像素坐标需要镜像
            def get_real_depth(landmark_pixel):
                # 翻转后的 X 坐标
                x_flipped = self.width - int(landmark_pixel.x * self.width)
                y = int(landmark_pixel.y * self.height)
                return self.get_depth_at_pixel(depth_frame, x_flipped, y)

            shoulder_depth = get_real_depth(left_shoulder_pixel)
            elbow_depth = get_real_depth(left_elbow_pixel)
            wrist_depth = get_real_depth(left_wrist_pixel)
            index_depth = get_real_depth(left_index_pixel)
            pinky_depth = get_real_depth(left_pinky_pixel)

            # 调试：统计深度有效性
            depths = [shoulder_depth, elbow_depth, wrist_depth, index_depth, pinky_depth]
            valid_depths = [d for d in depths if d is not None]
            self.depth_stats['valid_count'] += len(valid_depths)
            self.depth_stats['invalid_count'] += (len(depths) - len(valid_depths))
            if valid_depths:
                self.depth_stats['avg_depth'] = np.mean(valid_depths)

            # 3. 计算相对位置（局部坐标）
            elbow_local_mp = np.array([left_elbow_world.x, left_elbow_world.y, left_elbow_world.z]) - origin_mp
            wrist_local_mp = np.array([left_wrist_world.x, left_wrist_world.y, left_wrist_world.z]) - origin_mp
            index_local_mp = np.array([left_index_world.x, left_index_world.y, left_index_world.z]) - origin_mp
            pinky_local_mp = np.array([left_pinky_world.x, left_pinky_world.y, left_pinky_world.z]) - origin_mp

            # 4. 坐标系转换（MediaPipe → Robot）
            # ⚠️ 关键改进：使用 RealSense 深度替换 MediaPipe 的 Z 坐标
            # 计算相对深度（相对于肩部）
            shoulder_robot = np.array([0.0, 0.0, 0.0])  # 肩部固定在原点

            # 如果深度有效，计算相对深度；否则使用 MediaPipe 的估计
            elbow_rel_depth = (elbow_depth - shoulder_depth) if (elbow_depth and shoulder_depth) else None
            wrist_rel_depth = (wrist_depth - shoulder_depth) if (wrist_depth and shoulder_depth) else None
            index_rel_depth = (index_depth - shoulder_depth) if (index_depth and shoulder_depth) else None
            pinky_rel_depth = (pinky_depth - shoulder_depth) if (pinky_depth and shoulder_depth) else None

            # 调试输出：检查深度数据
            if hasattr(self, '_depth_debug_counter'):
                self._depth_debug_counter += 1
            else:
                self._depth_debug_counter = 0
            if self._depth_debug_counter % 30 == 0:  # 每30帧输出一次
                print(f"[DEPTH] shoulder={shoulder_depth:.4f}m, wrist={wrist_depth:.4f}m, rel={wrist_rel_depth:.4f}m" if wrist_rel_depth else "[DEPTH] wrist_rel_depth is None")

            elbow_robot = self.mediapipe_to_robot_coords(elbow_local_mp, elbow_rel_depth)
            wrist_robot = self.mediapipe_to_robot_coords(wrist_local_mp, wrist_rel_depth)
            index_robot = self.mediapipe_to_robot_coords(index_local_mp, index_rel_depth)
            pinky_robot = self.mediapipe_to_robot_coords(pinky_local_mp, pinky_rel_depth)

            # 5. 构建关键点字典（发送给 ArmNode）
            keypoints = {
                'shoulder': shoulder_robot.tolist(),  # [0, 0, 0]
                'elbow': elbow_robot.tolist(),
                'wrist': wrist_robot.tolist(),
                'index_mcp': index_robot.tolist(),
                'pinky_mcp': pinky_robot.tolist()
            }

            # 绘制姿态骨架（使用屏幕坐标）
            self.mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
            )

            # 绘制关键点标注（带深度信息）
            h, w, _ = frame.shape
            shoulder_xy = (int(left_shoulder_pixel.x * w), int(left_shoulder_pixel.y * h))
            elbow_xy = (int(left_elbow_pixel.x * w), int(left_elbow_pixel.y * h))
            wrist_xy = (int(left_wrist_pixel.x * w), int(left_wrist_pixel.y * h))

            # 绘制标签（包含深度信息）
            def draw_label_with_depth(frame, text, pos, depth):
                depth_str = f"{depth*1000:.0f}mm" if depth else "N/A"
                label = f"{text} ({depth_str})"
                cv2.putText(frame, label, pos, cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

            draw_label_with_depth(frame, "Shoulder", shoulder_xy, shoulder_depth)
            draw_label_with_depth(frame, "Elbow", elbow_xy, elbow_depth)
            draw_label_with_depth(frame, "Wrist", wrist_xy, wrist_depth)

        else:
            # 未检测到姿态
            cv2.putText(frame, "No pose detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # 计算并显示 FPS
        self.frame_count += 1
        elapsed = time.time() - self.fps_start_time
        if elapsed > 1.0:
            self.fps = self.frame_count / elapsed
            self.frame_count = 0
            self.fps_start_time = time.time()

        # 显示 FPS 和深度统计
        cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, frame.shape[0] - 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        total = self.depth_stats['valid_count'] + self.depth_stats['invalid_count']
        if total > 0:
            valid_rate = self.depth_stats['valid_count'] / total * 100
            cv2.putText(frame, f"Depth: {self.depth_stats['avg_depth']*1000:.0f}mm ({valid_rate:.0f}%)",
                       (10, frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return frame, keypoints

    def send_keypoints(self, keypoints):
        """
        通过 UDP 发送关键点数据（带时间戳）
        :param keypoints: 关键点字典
        """
        if keypoints is None:
            return

        try:
            # 添加时间戳（用于检测数据过期）
            packet = {
                'keypoints': keypoints,
                'timestamp': time.time()
            }
            data = json.dumps(packet).encode('utf-8')
            self.sock.sendto(data, self.udp_addr)
        except Exception as e:
            print(f"⚠️ [VisionNodeDepth] UDP 发送失败: {e}")

    def run(self, show_window=True):
        """
        运行视觉节点主循环
        :param show_window: 是否显示可视化窗口
        """
        print("🚀 [VisionNodeDepth] 开始运行...")
        print("   按 'q' 或 ESC 退出")

        try:
            while True:
                # 处理一帧
                frame, keypoints = self.process_frame()

                if frame is None:
                    continue

                # 发送关键点数据
                if keypoints is not None:
                    self.send_keypoints(keypoints)

                # 显示窗口
                if show_window:
                    cv2.imshow("VIST Vision Node - Pose + Depth", frame)

                    # 按键处理
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:  # 'q' 或 ESC
                        break

        except KeyboardInterrupt:
            print("\n⏹️ [VisionNodeDepth] 收到停止信号")

        finally:
            # 清理资源
            self.pipeline.stop()
            self.pose.close()
            self.sock.close()
            if show_window:
                cv2.destroyAllWindows()
            print("✅ [VisionNodeDepth] 已退出")


if __name__ == "__main__":
    # 创建并运行视觉节点（带深度）
    node = VisionNodeWithDepth(
        udp_ip="127.0.0.1",
        udp_port=6001,
        scale=1.0,  # 可调整灵敏度
        width=640,
        height=480,
        fps=30
    )
    node.run(show_window=True)
