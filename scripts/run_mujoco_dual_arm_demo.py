#!/usr/bin/env python3
"""
VIST MuJoCo 双臂仿真演示

数据流：
  电脑摄像头 → MediaPipe 双臂姿态检测 → 双 VIST 算法 → MuJoCo 双臂仿真

用法:
    MUJOCO_GL=glfw LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 \
        python3 scripts/run_mujoco_dual_arm_demo.py
"""

import sys
import os

# 修复 EGL 驱动路径
if "MUJOCO_GL" not in os.environ:
    os.environ["MUJOCO_GL"] = "egl"
if "LIBGL_DRIVERS_PATH" not in os.environ:
    os.environ["LIBGL_DRIVERS_PATH"] = "/usr/lib/x86_64-linux-gnu/dri"

import argparse
import time
import numpy as np
import cv2

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src", "nodes"))

# 导入 MediaPipe
import mediapipe_compat
import mediapipe as mp

# 导入 VIST 组件
from src.config import get_config
from src.control.vist_controller import VISTController
from src.robot.mujoco_arm_driver import MuJoCoArmDriver


class DualArmWebcamVisionNode:
    """
    双臂电脑摄像头视觉节点
    同时跟踪左右手臂
    """

    def __init__(self, camera_id: int = 0, scale: float = 1.0):
        self.camera_id = camera_id
        self.scale = scale

        # 初始化 MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            smooth_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils

        # 打开摄像头
        self.cap = cv2.VideoCapture(camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开摄像头 {camera_id}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.calibrated = False
        print(f"📷 [DualArmVision] 摄像头 {camera_id} 已打开")

    def get_dual_arm_keypoints(self):
        """
        获取双臂关键点

        Returns:
            (left_keypoints, right_keypoints, frame)
            - left_keypoints: 左臂关键点（肩部坐标系）
            - right_keypoints: 右臂关键点（肩部坐标系）
            - frame: 带标注的图像帧
        """
        ret, frame = self.cap.read()
        if not ret:
            return None, None, None

        # 水平翻转（镜像）
        frame = cv2.flip(frame, 1)

        # MediaPipe 处理
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)

        if not results.pose_landmarks:
            cv2.putText(frame, "No pose detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return None, None, frame

        landmarks = results.pose_landmarks.landmark
        h, w = frame.shape[:2]

        try:
            # MediaPipe 关键点索引（镜像后）：
            # 11=左肩（物理右侧）, 12=右肩（物理左侧）
            # 13=左肘, 14=右肘, 15=左腕, 16=右腕

            # 获取双肩位置
            l_shoulder = landmarks[11]  # 物理右侧
            r_shoulder = landmarks[12]  # 物理左侧

            # 肩宽用于尺度估算
            shoulder_width = abs(r_shoulder.x - l_shoulder.x)
            real_shoulder_width = 0.45
            scale_factor = real_shoulder_width / (shoulder_width + 1e-6) * self.scale

            # 定义坐标转换函数
            def to_shoulder_frame(pos, shoulder_pos):
                rel = (pos - shoulder_pos) * scale_factor
                return np.array([
                    -rel[1],   # x_shoulder = -y_mediapipe (上)
                     rel[0],   # y_shoulder = x_mediapipe (右)
                    -rel[2]    # z_shoulder = -z_mediapipe (前)
                ])

            # 处理左臂（物理右侧，对应仿真右臂）
            l_elbow = landmarks[13]
            l_wrist = landmarks[15]

            l_shoulder_pos = np.array([l_shoulder.x, l_shoulder.y, l_shoulder.z])
            l_elbow_pos = np.array([l_elbow.x, l_elbow.y, l_elbow.z])
            l_wrist_pos = np.array([l_wrist.x, l_wrist.y, l_wrist.z])

            l_elbow_rel = to_shoulder_frame(l_elbow_pos, l_shoulder_pos)
            l_wrist_rel = to_shoulder_frame(l_wrist_pos, l_shoulder_pos)

            # 手部关键点估算
            l_forearm_vec = l_wrist_rel - l_elbow_rel
            l_forearm_norm = l_forearm_vec / (np.linalg.norm(l_forearm_vec) + 1e-6)
            l_hand_right = np.array([l_forearm_norm[1], -l_forearm_norm[0], 0])
            l_hand_right = l_hand_right / (np.linalg.norm(l_hand_right) + 1e-6)

            left_keypoints = {
                'shoulder': np.zeros(3),
                'elbow': l_elbow_rel,
                'wrist': l_wrist_rel,
                'index_mcp': l_wrist_rel + l_forearm_norm * 0.10 + l_hand_right * 0.024,
                'pinky_mcp': l_wrist_rel + l_forearm_norm * 0.10 - l_hand_right * 0.024,
                'middle_tip': l_wrist_rel + l_forearm_norm * 0.15,
            }

            # 处理右臂（物理左侧，对应仿真左臂）
            r_elbow = landmarks[14]
            r_wrist = landmarks[16]

            r_shoulder_pos = np.array([r_shoulder.x, r_shoulder.y, r_shoulder.z])
            r_elbow_pos = np.array([r_elbow.x, r_elbow.y, r_elbow.z])
            r_wrist_pos = np.array([r_wrist.x, r_wrist.y, r_wrist.z])

            r_elbow_rel = to_shoulder_frame(r_elbow_pos, r_shoulder_pos)
            r_wrist_rel = to_shoulder_frame(r_wrist_pos, r_shoulder_pos)

            r_forearm_vec = r_wrist_rel - r_elbow_rel
            r_forearm_norm = r_forearm_vec / (np.linalg.norm(r_forearm_vec) + 1e-6)
            r_hand_right = np.array([r_forearm_norm[1], -r_forearm_norm[0], 0])
            r_hand_right = r_hand_right / (np.linalg.norm(r_hand_right) + 1e-6)

            right_keypoints = {
                'shoulder': np.zeros(3),
                'elbow': r_elbow_rel,
                'wrist': r_wrist_rel,
                'index_mcp': r_wrist_rel + r_forearm_norm * 0.10 + r_hand_right * 0.024,
                'pinky_mcp': r_wrist_rel + r_forearm_norm * 0.10 - r_hand_right * 0.024,
                'middle_tip': r_wrist_rel + r_forearm_norm * 0.15,
            }

            # 绘制骨架
            self.mp_drawing.draw_landmarks(
                frame, results.pose_landmarks, self.mp_pose.POSE_CONNECTIONS
            )

            # 显示信息
            cv2.putText(frame, f"Left arm (sim right): wrist={l_wrist_rel[:2]}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(frame, f"Right arm (sim left): wrist={r_wrist_rel[:2]}",
                       (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            return left_keypoints, right_keypoints, frame

        except Exception as e:
            cv2.putText(frame, f"Error: {str(e)[:40]}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            return None, None, frame

    def release(self):
        self.cap.release()
        self.pose.close()


class DualArmMuJoCoDriver:
    """
    双臂 MuJoCo 驱动
    同时控制左右手臂
    """

    def __init__(self, model_path: str, use_viewer: bool = True, debug: bool = False):
        self.model_path = model_path
        self.use_viewer = use_viewer
        self.debug = debug

        # 导入 MuJoCo
        import mujoco
        import mujoco.viewer

        self.model = None
        self.data = None
        self.viewer = None

        # 左臂和右臂的关节地址
        self.left_qpos_addrs = []
        self.left_dof_addrs = []
        self.right_qpos_addrs = []
        self.right_dof_addrs = []

        self._debug_count = 0

    def connect(self):
        import mujoco
        import mujoco.viewer

        self.model = mujoco.MjModel.from_xml_path(self.model_path)
        self.data = mujoco.MjData(self.model)

        # 查找左臂关节
        left_joint_names = [
            "Left_Shoulder_Pitch_Joint", "Left_Shoulder_Roll_Joint",
            "Left_Shoulder_Yaw_Joint", "Left_Elbow_Pitch_Joint",
            "Left_Wrist_Yaw_Joint", "Left_Wrist_Pitch_Joint", "Left_Wrist_Roll_Joint"
        ]
        for name in left_joint_names:
            jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)
            self.left_qpos_addrs.append(self.model.jnt_qposadr[jid])
            self.left_dof_addrs.append(self.model.jnt_dofadr[jid])

        # 查找右臂关节
        right_joint_names = [
            "Right_Shoulder_Pitch_Joint", "Right_Shoulder_Roll_Joint",
            "Right_Shoulder_Yaw_Joint", "Right_Elbow_Pitch_Joint",
            "Right_Wrist_Yaw_Joint", "Right_Wrist_Pitch_Joint", "Right_Wrist_Roll_Joint"
        ]
        for name in right_joint_names:
            jid = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, name)
            self.right_qpos_addrs.append(self.model.jnt_qposadr[jid])
            self.right_dof_addrs.append(self.model.jnt_dofadr[jid])

        print(f"[DualArmDriver] Left arm qpos: {self.left_qpos_addrs}")
        print(f"[DualArmDriver] Right arm qpos: {self.right_qpos_addrs}")

        # 禁用重力
        self.model.opt.gravity[:] = 0.0

        # 启动可视化
        if self.use_viewer:
            self.viewer = mujoco.viewer.launch_passive(self.model, self.data)

        mujoco.mj_resetData(self.model, self.data)
        return True

    def send_dual_command(self, q_left: np.ndarray, q_right: np.ndarray):
        """
        发送双臂控制指令

        Args:
            q_left: 左臂关节角（7维）
            q_right: 右臂关节角（7维）
        """
        import mujoco

        # 设置左臂
        if q_left is not None and len(q_left) == 7:
            self.data.qpos[self.left_qpos_addrs] = q_left
            self.data.qvel[self.left_dof_addrs] = 0.0

        # 设置右臂
        if q_right is not None and len(q_right) == 7:
            self.data.qpos[self.right_qpos_addrs] = q_right
            self.data.qvel[self.right_dof_addrs] = 0.0

        # 清零外力
        self.data.qfrc_applied[:] = 0.0

        # 推进仿真
        mujoco.mj_step(self.model, self.data)

        # 更新可视化
        if self.viewer is not None and self.viewer.is_running():
            self.viewer.sync()

        # 调试输出
        if self.debug and self._debug_count % 50 == 0:
            print(f"\n[DEBUG DualArm #{self._debug_count}]")
            if q_left is not None:
                print(f"  Left arm: {np.round(np.rad2deg(q_left[:4]), 1)}")
            if q_right is not None:
                print(f"  Right arm: {np.round(np.rad2deg(q_right[:4]), 1)}")
        self._debug_count += 1

    def disconnect(self):
        if self.viewer:
            self.viewer.close()


def main():
    parser = argparse.ArgumentParser(description="VIST MuJoCo 双臂仿真演示")
    parser.add_argument("--camera", type=int, default=0, help="摄像头 ID")
    parser.add_argument("--no-viewer", action="store_true", help="禁用 MuJoCo 可视化")
    parser.add_argument("--duration", type=float, default=300.0, help="运行时长（秒）")
    args = parser.parse_args()

    print("=" * 70)
    print("🎮 VIST MuJoCo 双臂仿真演示")
    print("=" * 70)

    # 加载配置
    config = get_config()

    # 初始化视觉节点
    print("\n📷 初始化双臂视觉节点...")
    vision = DualArmWebcamVisionNode(camera_id=args.camera, scale=config.vision_scale)

    # 初始化双 VIST 控制器
    print("\n🧠 初始化双 VIST 控制器...")

    # 创建左臂配置（修改末端执行器为左臂）
    import copy
    left_config = copy.deepcopy(config)
    left_config._config['hardware']['arm_side'] = 'left'

    # 镜像左臂的关节方向
    # 对于镜像对称的双臂机器人，只需要翻转左右对称的关节：
    # Joint 1 (Shoulder_Roll): 左右对称，需要翻转
    left_joint_dirs = left_config._config['robot']['joint_directions'].copy()
    left_joint_dirs[1] = -left_joint_dirs[1]  # Shoulder_Roll 翻转
    left_config._config['robot']['joint_directions'] = left_joint_dirs

    # 创建右臂配置（保持原配置）
    right_config = config

    left_controller = VISTController(left_config)   # 控制仿真左臂
    right_controller = VISTController(right_config)  # 控制仿真右臂

    print(f"✅ 左臂控制器: {left_config.robot_model_end_effector_frame}")
    print(f"✅ 右臂控制器: {right_config.robot_model_end_effector_frame}")

    # 初始化 MuJoCo 驱动
    print("\n🎮 初始化 MuJoCo 双臂驱动...")
    from pathlib import Path
    model_path = str(Path(project_root) / "config" / config.robot_model_urdf_file)
    driver = DualArmMuJoCoDriver(model_path, use_viewer=not args.no_viewer, debug=True)
    driver.connect()

    print("\n✅ 所有组件初始化完成！")
    print("=" * 70)
    print("\n操作说明：")
    print("  - 站在摄像头前，举起双臂")
    print("  - 现实左臂 → 仿真右臂")
    print("  - 现实右臂 → 仿真左臂")
    print("  - 按 'q' 退出\n")

    start_time = time.time()
    frame_count = 0

    try:
        while time.time() - start_time < args.duration:
            # 获取双臂关键点
            left_kp, right_kp, frame = vision.get_dual_arm_keypoints()

            # 调试：显示检测状态
            if frame_count % 50 == 0:
                print(f"\n[视觉检测] left_kp={'✓' if left_kp is not None else '✗'}, right_kp={'✓' if right_kp is not None else '✗'}")

            # 显示摄像头画面
            if frame is not None:
                cv2.imshow("VIST Dual Arm Demo", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            frame_count += 1

            # VIST 控制器处理
            q_left = None
            q_right = None

            if right_kp is not None:  # 现实右臂 → 仿真左臂
                try:
                    result = left_controller.process(right_kp)
                    if result is None:
                        if frame_count % 50 == 0:
                            print(f"⚠️ 左臂控制器返回 None")
                        q_left = None
                    else:
                        q_left, success, _ = result
                        if not success:
                            if frame_count % 50 == 0:
                                print(f"⚠️ 左臂控制器求解失败 (success=False)")
                            q_left = None
                        elif q_left is not None and frame_count % 50 == 0:
                            print(f"✓ 左臂控制器成功: q={np.round(np.rad2deg(q_left[:4]), 1)}")
                except Exception as e:
                    if frame_count % 50 == 0:
                        print(f"⚠️ 左臂控制器异常: {e}")
                    import traceback
                    if frame_count % 50 == 0:
                        traceback.print_exc()
                    pass

            if left_kp is not None:  # 现实左臂 → 仿真右臂
                try:
                    q_right, success, _ = right_controller.process(left_kp)
                    if not success:
                        if frame_count % 50 == 0:
                            print(f"⚠️ 右臂控制器求解失败")
                        q_right = None
                except Exception as e:
                    if frame_count % 50 == 0:
                        print(f"⚠️ 右臂控制器异常: {e}")
                    pass

            # 发送到 MuJoCo
            driver.send_dual_command(q_left, q_right)

            time.sleep(config.control_dt)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")

    finally:
        cv2.destroyAllWindows()
        vision.release()
        driver.disconnect()
        print("✅ 演示结束")


if __name__ == "__main__":
    main()
