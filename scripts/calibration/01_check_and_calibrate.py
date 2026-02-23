#!/usr/bin/env python3
# 文件名: 01_check_and_calibrate.py
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import math
import sys
import os
import time

# 导入 SDK
try:
    from lbot.lbot_robot import LbotRobot, LbotArm
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from lbot.lbot_robot import LbotRobot, LbotArm

# ================= 配置区 (请先修改这里) =================
# 1. 你的主端 Topic 名字 (通过 ros2 topic list 获取)
TOPIC_NAME = '/right_arm_joint_control' 

# 2. 机械臂 IP
ROBOT_IP = "192.168.10.21"

# 3. 主端关节索引 (根据之前截图，假设是 ID 0-6 或 7-13)
# 请观察终端打印，看哪几个数字在变
MASTER_INDICES = [0, 1, 2, 3, 4, 5, 6] 
# =======================================================

class CalibrationNode(Node):
    def __init__(self):
        super().__init__('calibration_node')
        self.get_logger().info("--- 开始校准模式 (不运动，只读取) ---")

        # 连接机械臂 (只连接，不使能)
        self.robot = LbotRobot(ROBOT_IP)
        if not self.robot.connect():
            self.get_logger().error("无法连接机械臂，请检查网线和IP！")
            sys.exit(1)
        
        self.get_logger().info("机械臂连接成功！正在读取当前姿态...")
        
        # 订阅
        self.sub = self.create_subscription(
            JointState, TOPIC_NAME, self.listener_callback, 10
        )

    def listener_callback(self, msg):
        # 获取机械臂当前的真实角度 (弧度 -> 角度)
        # 注意：这里假设控制的是右臂 RIGHT_ARM，如果是左臂请改为 LEFT_ARM
        slave_joints_rad = self.robot.get_joint_positions(LbotArm.RIGHT_ARM)
        
        if not slave_joints_rad:
            self.get_logger().warn("读取机械臂状态失败")
            return

        print("\n" + "="*50)
        print(f"【校准助手】请将以下计算出的 Offset 填入第二个脚本")
        print(f"{'关节':<5} | {'主端(Deg)':<12} | {'从端真值(Deg)':<12} | {'建议 Offset':<12}")
        print("-" * 50)

        calculated_offsets = []

        for i, idx in enumerate(MASTER_INDICES):
            if idx >= len(msg.position):
                continue
            
            # 1. 主端数据 (假设是角度)
            master_deg = msg.position[idx]
            
            # 2. 从端数据 (弧度转角度)
            slave_deg = math.degrees(slave_joints_rad[i])
            
            # 3. 计算偏置
            # 原理: 我们希望 (主端 - Offset) = 从端
            # 所以: Offset = 主端 - 从端
            offset = master_deg - slave_deg
            calculated_offsets.append(offset)

            print(f"J{i+1:<4} | {master_deg:>10.2f}   | {slave_deg:>10.2f}   | {offset:>10.2f}")

        print("="*50)
        print(f"请复制这行数组到脚本二: \nself.offsets_deg = {calculated_offsets}")
        # 降低打印频率
        time.sleep(0.5)

    def destroy_node(self):
        self.robot.disconnect()
        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = CalibrationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()