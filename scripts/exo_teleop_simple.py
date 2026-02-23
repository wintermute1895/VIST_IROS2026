#!/usr/bin/env python3
"""
外骨骼遥操作 - 纯Python版本（无ROS2依赖）
Baseline 1: 无滤波（直接映射）

使用方法：
python3 exo_teleop_baseline.py
"""
import sys
import os
import time
import json
import numpy as np
from pathlib import Path

# 添加项目路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# 导入SDK（假设在项目中）
try:
    from src.robot.sdk.linkerarm.lbot.lbot_robot import LbotRobot, LbotArm
except ImportError:
    print("❌ 无法导入LbotRobot SDK")
    print("请确保SDK路径正确")
    sys.exit(1)

# ================= 配置 =================
ROBOT_IP = "192.168.10.21"

# 外骨骼关节偏置和方向
OFFSETS_DEG = [-0.004119873057300496, 0.001373291053840304, -13.000596788247721,
               -1.6018310785803116, 0.5993896722450033, -3.2981688975778303, 6.201220512458846]
DIRECTIONS = [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]

# 控制频率
CONTROL_FREQ = 100  # Hz
# ========================================

class ExoskeletonTeleop:
    def __init__(self, use_filter=False, filter_alpha=0.2):
        """
        初始化外骨骼遥操作

        Args:
            use_filter: 是否使用低通滤波器
            filter_alpha: 滤波器参数（0-1，越小越平滑）
        """
        print("="*60)
        print("外骨骼遥操作系统")
        print(f"模式: {'带滤波' if use_filter else '无滤波（Baseline）'}")
        print("="*60)

        self.use_filter = use_filter

        # 连接机械臂
        print(f"正在连接机械臂 {ROBOT_IP}...")
        self.robot = LbotRobot(ROBOT_IP)
        if not self.robot.connect():
            print("❌ 连接失败！")
            sys.exit(1)
        print("✅ 连接成功")

        # 使能机械臂
        print("正在使能机械臂...")
        self.robot.enable_arm(LbotArm.RIGHT_ARM, True)
        self.robot.clear_errors()
        print("✅ 机械臂已使能")

        # 初始化滤波器（如果需要）
        if self.use_filter:
            from src.control.filters import LowPassFilter
            self.lpf = LowPassFilter(alpha=filter_alpha, n_dims=7)

            # 获取初始位置并重置滤波器
            q_init = self.robot.get_joint_positions(LbotArm.RIGHT_ARM)
            if q_init:
                self.lpf.reset(np.array(q_init))
                print(f"✅ 低通滤波器初始化完成 (alpha={filter_alpha})")

        # 数据记录
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        mode_name = "filtered" if use_filter else "raw"
        self.log_file = log_dir / f"exo_{mode_name}_{timestamp}.jsonl"
        print(f"📝 数据记录: {self.log_file}")

        print("\n✅ 系统就绪！")
        print("⚠️  注意安全！按Ctrl+C停止")
        print("="*60)

    def get_exoskeleton_joints(self):
        """
        获取外骨骼关节角度

        TODO: 这里需要替换为实际的外骨骼数据读取方式
        可能的方式：
        1. 从ROS2 topic读取
        2. 从串口读取
        3. 从UDP读取
        4. 从共享内存读取

        Returns:
            list: 7个关节的角度（度）
        """
        # 示例：这里需要替换为实际的读取代码
        # 暂时返回机械臂当前位置作为演示
        q_robot = self.robot.get_joint_positions(LbotArm.RIGHT_ARM)
        if q_robot:
            # 转换为度
            return [np.degrees(q) for q in q_robot]
        return None

    def process_joints(self, exo_joints_deg):
        """
        处理外骨骼关节数据

        Args:
            exo_joints_deg: 外骨骼关节角度（度）

        Returns:
            np.ndarray: 处理后的关节角度（弧度）
        """
        target_joints_rad = []

        for i in range(7):
            # 1. 减去偏置
            target_deg = exo_joints_deg[i] - OFFSETS_DEG[i]

            # 2. 转弧度并应用方向
            val_rad = np.radians(target_deg) * DIRECTIONS[i]
            target_joints_rad.append(val_rad)

        return np.array(target_joints_rad)

    def run(self):
        """主控制循环"""
        dt = 1.0 / CONTROL_FREQ

        try:
            while True:
                loop_start = time.time()

                # 1. 获取外骨骼数据
                exo_joints_deg = self.get_exoskeleton_joints()
                if exo_joints_deg is None:
                    time.sleep(dt)
                    continue

                # 2. 处理关节数据
                q_target = self.process_joints(exo_joints_deg)

                # 3. 应用滤波器（如果启用）
                if self.use_filter:
                    q_filtered = self.lpf.update(q_target)
                    q_command = q_filtered
                else:
                    q_command = q_target

                # 4. 发送到机械臂
                self.robot.joint_follow(LbotArm.RIGHT_ARM, q_command.tolist(), follow=True)

                # 5. 记录数据
                self._log_data(q_target, q_command)

                # 6. 控制频率
                elapsed = time.time() - loop_start
                sleep_time = dt - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断")
        finally:
            self.cleanup()

    def _log_data(self, q_target, q_command):
        """记录数据"""
        q_actual = self.robot.get_joint_positions(LbotArm.RIGHT_ARM)

        log_entry = {
            'timestamp': time.time(),
            'q_target': q_target.tolist(),
            'q_command': q_command.tolist(),
            'q_actual': q_actual if q_actual else [],
            'mode': 'filtered' if self.use_filter else 'raw'
        }

        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')

    def cleanup(self):
        """清理资源"""
        print("\n正在停止...")
        self.robot.disconnect()
        print("✅ 已断开连接")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='外骨骼遥操作')
    parser.add_argument('--filter', action='store_true', help='启用低通滤波器')
    parser.add_argument('--alpha', type=float, default=0.2, help='滤波器参数（0-1）')

    args = parser.parse_args()

    teleop = ExoskeletonTeleop(use_filter=args.filter, filter_alpha=args.alpha)
    teleop.run()


if __name__ == '__main__':
    main()