#!/usr/bin/env python3
"""
Vision Node - MediaPipe Hands Integration
使用 MediaPipe Hands 检测手部关键点，生成虚拟肩部/肘部，并通过 UDP 发送给 ArmNode
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
        print("📷 [VisionNode] 初始化视觉节点...")

        # 摄像头
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开摄像头 {camera_id}")

        # 设置摄像头分辨率（可选，提高性能）
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,  # 只检测一只手
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
            model_complexity=1  # 0=Lite, 1=Full (更准确)
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
        MediaPipe: X右, Y下, Z向外（朝向用户）
        Robot: X前, Y左, Z上

        转换规则:
        x_robot = z_mp (深度 → 前方)
        y_robot = -x_mp (左右翻转)
        z_robot = -y_mp (上下翻转)

        :param mp_point: MediaPipe 世界坐标 [x, y, z]
        :return: 机器人坐标系 [x, y, z]
        """
        x_mp, y_mp, z_mp = mp_point
        return np.array([
            z_mp * self.scale,   # 深度 → 前方
            -x_mp * self.scale,  # 左右翻转
            -y_mp * self.scale   # 上下翻转
        ])

    def generate_virtual_arm(self, wrist_pos):
        """
        从手腕位置生成虚拟的肩部和肘部位置
        由于 MediaPipe Hands 只检测手部，我们需要生成虚拟的上臂关节

        策略：
        - 肩部：固定在手腕后方和上方（相对于机器人坐标系）
        - 肘部：在肩部和手腕之间

        :param wrist_pos: 手腕位置（机器人坐标系）
        :return: (shoulder_pos, elbow_pos)
        """
        # 虚拟肩部：在手腕后方 0.3m，上方 0.2m
        shoulder_offset = np.array([-0.3, 0.0, 0.2])
        shoulder_pos = wrist_pos + shoulder_offset

        # 虚拟肘部：在肩部和手腕中间偏后
        elbow_pos = shoulder_pos * 0.4 + wrist_pos * 0.6

        return shoulder_pos, elbow_pos

    def process_frame(self):
        """
        处理一帧图像
        :return: (annotated_frame, keypoints_dict) 或 (None, None) 如果失败
        """
        ret, frame = self.cap.read()
        if not ret:
            print("⚠️ [VisionNode] 无法读取摄像头帧")
            return None, None

        # 翻转图像（镜像模式，更自然）
        frame = cv2.flip(frame, 1)

        # 转换为 RGB（MediaPipe 需要）
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # MediaPipe 处理
        results = self.hands.process(rgb_frame)

        # 初始化关键点字典
        keypoints = None

        if results.multi_hand_landmarks and results.multi_hand_world_landmarks:
            # 获取第一只手的世界坐标
            hand_world_landmarks = results.multi_hand_world_landmarks[0]

            # 提取关键点（使用世界坐标，单位：米）
            wrist = hand_world_landmarks.landmark[0]  # 手腕
            index_mcp = hand_world_landmarks.landmark[5]  # 食指掌指关节
            pinky_mcp = hand_world_landmarks.landmark[17]  # 小指掌指关节

            # 转换为 numpy 数组
            wrist_mp = np.array([wrist.x, wrist.y, wrist.z])
            index_mcp_mp = np.array([index_mcp.x, index_mcp.y, index_mcp.z])
            pinky_mcp_mp = np.array([pinky_mcp.x, pinky_mcp.y, pinky_mcp.z])

            # 坐标系转换
            wrist_robot = self.mediapipe_to_robot_coords(wrist_mp)
            index_mcp_robot = self.mediapipe_to_robot_coords(index_mcp_mp)
            pinky_mcp_robot = self.mediapipe_to_robot_coords(pinky_mcp_mp)

            # 生成虚拟肩部和肘部
            shoulder_robot, elbow_robot = self.generate_virtual_arm(wrist_robot)

            # 构建关键点字典
            keypoints = {
                'shoulder': shoulder_robot.tolist(),
                'elbow': elbow_robot.tolist(),
                'wrist': wrist_robot.tolist(),
                'index_mcp': index_mcp_robot.tolist(),
                'pinky_mcp': pinky_mcp_robot.tolist()
            }

            # 绘制手部骨架（使用屏幕坐标）
            hand_landmarks = results.multi_hand_landmarks[0]
            self.mp_drawing.draw_landmarks(
                frame,
                hand_landmarks,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_drawing_styles.get_default_hand_landmarks_style(),
                self.mp_drawing_styles.get_default_hand_connections_style()
            )

            # 绘制关键点标注
            h, w, _ = frame.shape
            wrist_px = hand_landmarks.landmark[0]
            index_mcp_px = hand_landmarks.landmark[5]
            pinky_mcp_px = hand_landmarks.landmark[17]

            # 转换为像素坐标
            wrist_xy = (int(wrist_px.x * w), int(wrist_px.y * h))
            index_xy = (int(index_mcp_px.x * w), int(index_mcp_px.y * h))
            pinky_xy = (int(pinky_mcp_px.x * w), int(pinky_mcp_px.y * h))

            # 绘制标签
            cv2.putText(frame, "Wrist", wrist_xy, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(frame, "Index", index_xy, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            cv2.putText(frame, "Pinky", pinky_xy, cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        else:
            # 未检测到手
            cv2.putText(frame, "No hand detected", (10, 30),
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
        通过 UDP 发送关键点数据
        :param keypoints: 关键点字典
        """
        if keypoints is None:
            return

        try:
            # 转换为 JSON 并发送
            data = json.dumps(keypoints).encode('utf-8')
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
                    cv2.imshow("VIST Vision Node", frame)

                    # 按键处理
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:  # 'q' 或 ESC
                        break

        except KeyboardInterrupt:
            print("\n⏹️ [VisionNode] 收到停止信号")

        finally:
            # 清理资源
            self.cap.release()
            self.hands.close()
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

