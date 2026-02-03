#!/usr/bin/env python3
"""
Vision Node - MediaPipe Pose Integration with Dynamic Zeroing
使用 MediaPipe Pose 检测人体姿态，实现"动态归零"机制：
所有关键点相对于肩部原点，确保用户身体移动时机械臂基座不动
"""
import cv2
import mediapipe as mp
import numpy as np
import socket
import json
import time


class VisionNode:
    def __init__(self, camera_id=0, udp_ip="127.0.0.1", udp_port=6001, scale=1.0):
        """
        初始化视觉节点
        :param camera_id: 摄像头 ID
        :param udp_ip: UDP 目标 IP
        :param udp_port: UDP 目标端口
        :param scale: 缩放因子（调整灵敏度）
        """
        print("📷 [VisionNode] 初始化视觉节点 (MediaPipe Pose + Dynamic Zeroing)...")

        # 摄像头
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开摄像头 {camera_id}")

        # 设置摄像头分辨率
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # MediaPipe Pose (全身姿态检测)
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

        # UDP 发送器
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_addr = (udp_ip, udp_port)
        print(f"📡 [VisionNode] UDP 发送目标: {udp_ip}:{udp_port}")

        # 参数
        self.scale = scale

        # FPS 计算
        self.fps = 0
        self.frame_count = 0
        self.fps_start_time = time.time()

        print("✅ [VisionNode] 初始化完成")

    def mediapipe_to_robot_coords(self, mp_point):
        """
        将 MediaPipe 坐标系转换为机器人坐标系

        MediaPipe Pose World Landmarks:
        - X: 右（用户视角）
        - Y: 下
        - Z: 向外（背离相机，深度为负）

        Robot Base Frame:
        - X: 前
        - Y: 左
        - Z: 上

        转换规则（经过实验验证）:
        x_robot = -z_mp  (深度反向 → 前方)
        y_robot = -x_mp  (左右翻转)
        z_robot = -y_mp  (上下翻转)

        :param mp_point: MediaPipe 世界坐标 [x, y, z]
        :return: 机器人坐标系 [x, y, z]
        """
        x_mp, y_mp, z_mp = mp_point
        return np.array([
            -z_mp * self.scale,  # 深度反向 → 前方
            -x_mp * self.scale,  # 左右翻转
            -y_mp * self.scale   # 上下翻转
        ])

    def process_frame(self):
        """
        处理一帧图像 - 实现动态归零机制
        :return: (annotated_frame, keypoints_dict) 或 (None, None) 如果失败
        """
        ret, frame = self.cap.read()
        if not ret:
            print("⚠️ [VisionNode] 无法读取摄像头帧")
            return None, None

        # 翻转图像（镜像模式）
        frame = cv2.flip(frame, 1)

        # 转换为 RGB（MediaPipe 需要）
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # MediaPipe Pose 处理
        results = self.pose.process(rgb_frame)

        # 初始化关键点字典
        keypoints = None

        if results.pose_world_landmarks:
            # 获取世界坐标（单位：米）
            landmarks = results.pose_world_landmarks.landmark

            # ==========================================
            # 【动态归零】关键步骤
            # ==========================================
            # 1. 获取右肩作为原点（Landmark 12）
            right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
            origin_mp = np.array([right_shoulder.x, right_shoulder.y, right_shoulder.z])

            # 2. 获取其他关键点（相对于原点）
            right_elbow = landmarks[self.mp_pose.PoseLandmark.RIGHT_ELBOW.value]
            right_wrist = landmarks[self.mp_pose.PoseLandmark.RIGHT_WRIST.value]
            right_index = landmarks[self.mp_pose.PoseLandmark.RIGHT_INDEX.value]
            right_pinky = landmarks[self.mp_pose.PoseLandmark.RIGHT_PINKY.value]

            # 3. 计算相对位置（局部坐标）
            elbow_local_mp = np.array([right_elbow.x, right_elbow.y, right_elbow.z]) - origin_mp
            wrist_local_mp = np.array([right_wrist.x, right_wrist.y, right_wrist.z]) - origin_mp
            index_local_mp = np.array([right_index.x, right_index.y, right_index.z]) - origin_mp
            pinky_local_mp = np.array([right_pinky.x, right_pinky.y, right_pinky.z]) - origin_mp

            # 4. 坐标系转换（MediaPipe → Robot）
            shoulder_robot = np.array([0.0, 0.0, 0.0])  # 肩部固定在原点
            elbow_robot = self.mediapipe_to_robot_coords(elbow_local_mp)
            wrist_robot = self.mediapipe_to_robot_coords(wrist_local_mp)
            index_robot = self.mediapipe_to_robot_coords(index_local_mp)
            pinky_robot = self.mediapipe_to_robot_coords(pinky_local_mp)

            # 5. 构建关键点字典（发送给 ArmNode）
            keypoints = {
                'shoulder': shoulder_robot.tolist(),  # [0, 0, 0]
                'elbow': elbow_robot.tolist(),
                'wrist': wrist_robot.tolist(),
                'index_mcp': index_robot.tolist(),  # 使用指尖代替指关节
                'pinky_mcp': pinky_robot.tolist()
            }

            # 绘制姿态骨架（使用屏幕坐标）
            if results.pose_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    self.mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
                )

            # 绘制关键点标注
            h, w, _ = frame.shape
            if results.pose_landmarks:
                shoulder_px = results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_SHOULDER.value]
                elbow_px = results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_ELBOW.value]
                wrist_px = results.pose_landmarks.landmark[self.mp_pose.PoseLandmark.RIGHT_WRIST.value]

                # 转换为像素坐标
                shoulder_xy = (int(shoulder_px.x * w), int(shoulder_px.y * h))
                elbow_xy = (int(elbow_px.x * w), int(elbow_px.y * h))
                wrist_xy = (int(wrist_px.x * w), int(wrist_px.y * h))

                # 绘制标签
                cv2.putText(frame, "Shoulder (Origin)", shoulder_xy, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
                cv2.putText(frame, "Elbow", elbow_xy, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.putText(frame, "Wrist", wrist_xy, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

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

        cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, frame.shape[0] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

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
            print(f"⚠️ [VisionNode] UDP 发送失败: {e}")

    def run(self, show_window=True):
        """
        运行视觉节点主循环
        :param show_window: 是否显示可视化窗口
        """
        print("🚀 [VisionNode] 开始运行...")
        print("   按 'q' 或 ESC 退出")

        try:
            while True:
                # 处理一帧
                frame, keypoints = self.process_frame()

                if frame is None:
                    break

                # 发送关键点数据
                if keypoints is not None:
                    self.send_keypoints(keypoints)

                # 显示窗口
                if show_window:
                    cv2.imshow("VIST Vision Node - Pose Tracking", frame)

                    # 按键处理
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:  # 'q' 或 ESC
                        break

        except KeyboardInterrupt:
            print("\n⏹️ [VisionNode] 收到停止信号")

        finally:
            # 清理资源
            self.cap.release()
            self.pose.close()
            self.sock.close()
            if show_window:
                cv2.destroyAllWindows()
            print("✅ [VisionNode] 已退出")


if __name__ == "__main__":
    # 创建并运行视觉节点
    node = VisionNode(
        camera_id=0,
        udp_ip="127.0.0.1",
        udp_port=6001,
        scale=1.0  # 可调整灵敏度
    )
    node.run(show_window=True)

