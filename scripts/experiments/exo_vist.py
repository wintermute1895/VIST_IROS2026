#!/usr/bin/env python3
"""
外骨骼遥操作 - Ours: VIST + 低通滤波器
完整的VIST算法（如果需要意图因子，需要视觉输入）
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import math
import sys
import os
import time
import json
import numpy as np
from pathlib import Path

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    from lbot.lbot_robot import LbotRobot, LbotArm
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from lbot.lbot_robot import LbotRobot, LbotArm

from src.control.filters import LowPassFilter

# ================= 配置 =================
ROBOT_IP = "192.168.10.21"
TOPIC_NAME = '/right_arm_joint_control'
MASTER_INDICES = [0, 1, 2, 3, 4, 5, 6]
offsets_deg = [-0.004119873057300496, 0.001373291053840304, -13.000596788247721,
               -1.6018310785803116, 0.5993896722450033, -3.2981688975778303, 6.201220512458846]
directions = [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]

# 滤波器参数
FILTER_ALPHA = 0.2  # 强平滑（推荐）
# ========================================

class TeleopWithFilter(Node):
    def __init__(self):
        super().__init__('teleop_with_filter')
        self.get_logger().info(">>> Ours: VIST + 低通滤波器 <<<")

        # 连接机械臂
        self.robot = LbotRobot(ROBOT_IP)
        if not self.robot.connect():
            self.get_logger().error("连接失败！")
            sys.exit(1)

        self.robot.enable_arm(LbotArm.RIGHT_ARM, True)
        self.robot.clear_errors()

        # 初始化低通滤波器
        self.lpf = LowPassFilter(alpha=FILTER_ALPHA, n_dims=7)
        self.get_logger().info(f"低通滤波器初始化完成 (alpha={FILTER_ALPHA})")

        # 获取初始位置并重置滤波器
        q_init = self.robot.get_joint_positions(LbotArm.RIGHT_ARM)
        if q_init:
            self.lpf.reset(np.array(q_init))
            self.get_logger().info(f"滤波器已重置到初始位置")

        # 数据记录
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.log_file = log_dir / f"exo_ours_filtered_{timestamp}.jsonl"
        self.get_logger().info(f"数据记录: {self.log_file}")

        # 订阅
        self.sub = self.create_subscription(
            JointState, TOPIC_NAME, self.listener_callback, 10
        )
        self.get_logger().info(">>> 系统就绪！注意安全！ <<<")

    def listener_callback(self, msg):
        try:
            target_joints_rad = []

            for i, idx in enumerate(MASTER_INDICES):
                if idx >= len(msg.position): continue
                raw_deg = msg.position[idx]
                target_deg = (raw_deg - offsets_deg[i])
                val_rad = math.radians(target_deg) * directions[i]
                target_joints_rad.append(val_rad)

            if len(target_joints_rad) == 7:
                # 应用低通滤波器
                q_raw = np.array(target_joints_rad)
                q_filtered = self.lpf.update(q_raw)

                # 发送滤波后的指令
                self.robot.joint_follow(LbotArm.RIGHT_ARM, q_filtered.tolist(), follow=True)

                # 记录数据
                self._log_data(q_raw, q_filtered)

        except Exception as e:
            self.get_logger().error(f"Error: {e}")

    def _log_data(self, q_raw, q_filtered):
        """记录数据用于后续分析"""
        # 获取机械臂实际位置
        q_actual = self.robot.get_joint_positions(LbotArm.RIGHT_ARM)

        log_entry = {
            'timestamp': time.time(),
            'q_raw': q_raw.tolist(),
            'q_filtered': q_filtered.tolist(),
            'q_actual': q_actual if q_actual else [],
            'mode': 'ours_filtered',
            'filter_alpha': FILTER_ALPHA
        }

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def destroy_node(self):
        self.get_logger().info("正在停止...")
        self.robot.disconnect()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = TeleopWithFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()