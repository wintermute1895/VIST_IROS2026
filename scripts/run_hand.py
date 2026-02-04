#!/usr/bin/env python3
"""
LinkerHand 灵巧手测试脚本
支持两种模式：
1. Mock 模式：模拟手部关键点输入，测试驱动逻辑
2. Real 模式：使用 MediaPipe 捕获真实手部关键点，控制真机
"""

import sys
import os
import time
import argparse
import numpy as np

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.robot.hand_driver import create_hand_driver

# 尝试导入 MediaPipe 和 RealSense（仅 real 模式需要）
try:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    MEDIAPIPE_AVAILABLE = False
    print(f"⚠️  MediaPipe not available: {e}. Only mock mode is supported.")

try:
    import pyrealsense2 as rs
    REALSENSE_AVAILABLE = True
except ImportError as e:
    REALSENSE_AVAILABLE = False
    print(f"⚠️  RealSense not available: {e}. Will use standard camera.")


def generate_mock_keypoints(t):
    """
    生成模拟的手部关键点（用于测试）

    Args:
        t: float, 时间参数（用于生成动画效果）

    Returns:
        numpy array, shape (21, 3), 模拟的手部关键点
    """
    # 创建一个基础的手部姿态
    keypoints = np.zeros((21, 3))

    # 手腕（关键点 0）
    keypoints[0] = [0.0, 0.0, 0.0]

    # 拇指（关键点 1-4）
    keypoints[1] = [0.05, -0.02, 0.0]
    keypoints[2] = [0.08, -0.04, 0.0]
    keypoints[3] = [0.10, -0.06, 0.0]
    keypoints[4] = [0.12, -0.08, 0.0]

    # 食指（关键点 5-8）
    keypoints[5] = [0.03, 0.02, 0.0]
    keypoints[6] = [0.05, 0.05, 0.0]
    keypoints[7] = [0.06, 0.08, 0.0]
    keypoints[8] = [0.07, 0.11, 0.0]

    # 中指（关键点 9-12）
    keypoints[9] = [0.01, 0.03, 0.0]
    keypoints[10] = [0.01, 0.07, 0.0]
    keypoints[11] = [0.01, 0.11, 0.0]
    keypoints[12] = [0.01, 0.14, 0.0]

    # 无名指（关键点 13-16）
    keypoints[13] = [-0.01, 0.02, 0.0]
    keypoints[14] = [-0.02, 0.06, 0.0]
    keypoints[15] = [-0.03, 0.10, 0.0]
    keypoints[16] = [-0.04, 0.13, 0.0]

    # 小指（关键点 17-20）
    keypoints[17] = [-0.03, 0.01, 0.0]
    keypoints[18] = [-0.05, 0.04, 0.0]
    keypoints[19] = [-0.06, 0.07, 0.0]
    keypoints[20] = [-0.07, 0.10, 0.0]

    # 添加动画效果：手指弯曲
    bend_factor = (np.sin(t) + 1) / 2  # 0 到 1 之间

    # 让所有手指根据时间弯曲
    for i in range(5, 21):  # 跳过手腕和拇指根部
        keypoints[i, 1] *= (0.5 + 0.5 * bend_factor)

    return keypoints


def run_mock_mode(driver, duration=10.0, fps=30):
    """
    运行 Mock 模式测试

    Args:
        driver: HandDriver 实例
        duration: float, 测试持续时间（秒）
        fps: int, 帧率
    """
    print(f"\n🎮 Running in MOCK mode for {duration} seconds...")
    print("Generating simulated hand keypoints with animation...")

    start_time = time.time()
    frame_count = 0

    try:
        while time.time() - start_time < duration:
            # 生成模拟关键点
            t = time.time() - start_time
            keypoints = generate_mock_keypoints(t)

            # 发送到驱动
            driver.process_keypoints(keypoints)

            frame_count += 1
            if frame_count % fps == 0:
                print(f"  ⏱️  {int(t)}s - Frame {frame_count}")

            # 控制帧率
            time.sleep(1.0 / fps)

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")

    print(f"\n✅ Mock mode test completed. Total frames: {frame_count}")


def run_real_mode(driver, camera_id=0, fps=30, use_realsense=True):
    """
    运行 Real 模式：使用 MediaPipe 捕获真实手部关键点

    Args:
        driver: HandDriver 实例
        camera_id: int, 相机设备 ID（仅用于普通相机）
        fps: int, 目标帧率
        use_realsense: bool, 是否使用 RealSense D435i
    """
    if not MEDIAPIPE_AVAILABLE:
        print("❌ MediaPipe is not available. Cannot run in real mode.")
        return

    if use_realsense and not REALSENSE_AVAILABLE:
        print("⚠️  RealSense not available, falling back to standard camera")
        use_realsense = False

    print(f"\n📹 Running in REAL mode with {'RealSense D435i' if use_realsense else f'camera {camera_id}'}...")
    print("Press 'q' to quit")

    # 初始化 MediaPipe HandLandmarker (新 API)
    base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
    options = vision.HandLandmarkerOptions(
        base_options=base_options,
        num_hands=1,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )
    detector = vision.HandLandmarker.create_from_options(options)

    # 初始化相机
    if use_realsense:
        # 配置 RealSense D435i
        pipeline = rs.pipeline()
        config = rs.config()

        # 配置彩色流（用于手部检测）
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, fps)

        # 启动管道
        print("🎥 Starting RealSense D435i pipeline...")
        pipeline.start(config)
        print("✅ RealSense D435i initialized")

        cap = None
    else:
        # 使用普通相机
        cap = cv2.VideoCapture(camera_id)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        if not cap.isOpened():
            print(f"❌ Cannot open camera {camera_id}")
            return

        print("✅ Camera opened successfully")
        pipeline = None

    print("✅ MediaPipe HandLandmarker initialized")
    print("\n👋 Show your hand to the camera...")

    frame_count = 0
    detection_count = 0

    try:
        while True:
            # 读取帧
            if use_realsense:
                # 从 RealSense 读取
                frames = pipeline.wait_for_frames()
                color_frame = frames.get_color_frame()
                if not color_frame:
                    print("❌ Failed to read RealSense frame")
                    continue

                # 转换为 numpy 数组
                frame = np.asanyarray(color_frame.get_data())
            else:
                # 从普通相机读取
                ret, frame = cap.read()
                if not ret:
                    print("❌ Failed to read frame")
                    break

            # 翻转图像（镜像效果）
            frame = cv2.flip(frame, 1)

            # 转换为 MediaPipe Image 格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # 检测手部
            detection_result = detector.detect(mp_image)

            # 处理检测结果
            if detection_result.hand_landmarks:
                for hand_landmarks in detection_result.hand_landmarks:
                    # 提取关键点坐标
                    keypoints = np.zeros((21, 3))
                    for i, landmark in enumerate(hand_landmarks):
                        keypoints[i] = [landmark.x, landmark.y, landmark.z]

                    # 发送到驱动
                    driver.process_keypoints(keypoints)
                    detection_count += 1

                    # 在图像上绘制关键点
                    for i, landmark in enumerate(hand_landmarks):
                        x = int(landmark.x * frame.shape[1])
                        y = int(landmark.y * frame.shape[0])
                        cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)

            # 显示帧数和检测状态
            status_text = f"Frame: {frame_count} | Detected: {detection_count}"
            cv2.putText(frame, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            if detection_result.hand_landmarks:
                cv2.putText(frame, "Hand Detected!", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "No Hand", (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # 显示图像
            cv2.imshow('LinkerHand Control', frame)

            frame_count += 1

            # 检查退出
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            # 控制帧率
            time.sleep(1.0 / fps)

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 清理资源
        if use_realsense and pipeline:
            pipeline.stop()
            print("🛑 RealSense pipeline stopped")
        if cap:
            cap.release()
        cv2.destroyAllWindows()

    print(f"\n✅ Real mode completed.")
    print(f"   Total frames: {frame_count}")
    print(f"   Detections: {detection_count}")
    if frame_count > 0:
        print(f"   Detection rate: {detection_count/frame_count*100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description='LinkerHand 灵巧手测试脚本')
    parser.add_argument('--mode', type=str, default='mock', choices=['mock', 'real'],
                       help='运行模式：mock（模拟）或 real（真机）')
    parser.add_argument('--config', type=str,
                       default='config/hand_retargeting_config.yaml',
                       help='配置文件路径（仅 real 模式需要）')
    parser.add_argument('--camera', type=int, default=0,
                       help='相机设备 ID（仅 real 模式需要，不使用 RealSense 时）')
    parser.add_argument('--use-realsense', action='store_true', default=True,
                       help='使用 Intel RealSense D435i 深度相机（默认启用）')
    parser.add_argument('--no-realsense', action='store_false', dest='use_realsense',
                       help='不使用 RealSense，使用普通相机')
    parser.add_argument('--duration', type=float, default=10.0,
                       help='测试持续时间（秒，仅 mock 模式）')
    parser.add_argument('--fps', type=int, default=30,
                       help='目标帧率')

    args = parser.parse_args()

    print("=" * 60)
    print("🖐️  LinkerHand 灵巧手测试脚本")
    print("=" * 60)
    print(f"模式: {args.mode.upper()}")
    print(f"配置文件: {args.config}")
    if args.mode == 'real':
        if args.use_realsense:
            print(f"相机: Intel RealSense D435i")
        else:
            print(f"相机: 标准相机 (ID: {args.camera})")
    print(f"帧率: {args.fps} FPS")
    print("=" * 60)

    # 创建驱动实例
    try:
        if args.mode == 'mock':
            print("\n📦 Creating Mock driver...")
            driver = create_hand_driver(mode='mock')
        else:
            print(f"\n📦 Creating Real driver with config: {args.config}")
            config_path = os.path.join(PROJECT_ROOT, args.config)
            driver = create_hand_driver(
                mode='real',
                config_path=config_path,
                project_root=PROJECT_ROOT
            )
    except Exception as e:
        print(f"\n❌ Failed to create driver: {e}")
        import traceback
        traceback.print_exc()
        return

    # 运行测试
    try:
        if args.mode == 'mock':
            run_mock_mode(driver, duration=args.duration, fps=args.fps)
        else:
            run_real_mode(driver, camera_id=args.camera, fps=args.fps,
                         use_realsense=args.use_realsense)
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理
        if hasattr(driver, 'close'):
            driver.close()

    print("\n" + "=" * 60)
    print("🛑 Test completed")
    print("=" * 60)


if __name__ == "__main__":
    main()