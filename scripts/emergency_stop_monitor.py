#!/usr/bin/env python3
"""
紧急停止监控脚本
提供多种紧急停止机制，确保真机测试安全

功能：
1. 键盘监听（ESC 键紧急停止）
2. 数据超时检测
3. 异常状态检测
4. 发送零速度命令

使用方法：
1. 单独运行：python emergency_stop_monitor.py --ip 192.168.1.183
2. 配合真机控制脚本运行（在另一个终端）

Author: VIST Project
Date: 2026-02-07
"""

import os
import sys
import time
import threading
import numpy as np

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.robot.arm_driver import RealArmDriver


class EmergencyStopMonitor:
    """紧急停止监控器"""

    def __init__(self, robot_ip="192.168.1.183", arm_side="right"):
        """
        初始化监控器

        Args:
            robot_ip: 机器人控制器 IP 地址
            arm_side: 使用哪个手臂
        """
        self.robot_ip = robot_ip
        self.arm_side = arm_side
        self.driver = None
        self.stop_flag = False
        self.emergency_triggered = False

        print("=" * 80)
        print("🚨 紧急停止监控器")
        print("=" * 80)

    def connect(self):
        """连接到真机"""
        print(f"\n🔌 连接机器人 ({self.robot_ip})...")
        self.driver = RealArmDriver(
            ip=self.robot_ip,
            dof=7,
            arm_side=self.arm_side
        )

        success = self.driver.connect()
        if not success:
            raise RuntimeError("❌ 连接机器人失败！")

        print("✅ 连接成功")

    def send_stop_command(self):
        """发送停止命令（保持当前位置）"""
        if self.driver is None:
            print("⚠️ 驱动器未初始化")
            return

        try:
            # 读取当前位置
            _, q_current, _ = self.driver.get_state()

            # 发送当前位置（停止运动）
            self.driver.send_command(q_current)
            print("✅ 停止命令已发送")
        except Exception as e:
            print(f"❌ 发送停止命令失败: {e}")

    def keyboard_monitor(self):
        """键盘监听线程（ESC 键紧急停止）"""
        print("\n⌨️  键盘监听已启动")
        print("   按 ESC 键触发紧急停止")
        print("   按 Ctrl+C 退出监控器\n")

        try:
            # 尝试导入 keyboard 库
            import keyboard

            while not self.stop_flag:
                if keyboard.is_pressed('esc'):
                    print("\n🚨 检测到 ESC 键！触发紧急停止！")
                    self.emergency_triggered = True
                    self.send_stop_command()
                    break
                time.sleep(0.01)

        except ImportError:
            print("⚠️ keyboard 库未安装，键盘监听功能不可用")
            print("   安装方法: pip install keyboard")
            print("   注意：可能需要 root 权限运行")

            # 降级方案：使用 input() 等待用户输入
            print("\n💡 降级方案：输入 'stop' 并按回车触发紧急停止")
            while not self.stop_flag:
                try:
                    user_input = input()
                    if user_input.lower() in ['stop', 'esc', 'quit', 'exit']:
                        print("\n🚨 触发紧急停止！")
                        self.emergency_triggered = True
                        self.send_stop_command()
                        break
                except EOFError:
                    break

    def state_monitor(self, check_interval=0.1):
        """状态监控线程（检测异常状态）"""
        print("📊 状态监控已启动")
        print(f"   检查间隔: {check_interval}秒\n")

        last_state_time = time.time()
        timeout_threshold = 2.0  # 2秒无状态更新视为超时

        while not self.stop_flag and not self.emergency_triggered:
            try:
                # 读取机器人状态
                timestamp, q_pos, q_vel = self.driver.get_state()

                # 检查状态是否有效
                if np.allclose(q_pos, 0.0, atol=1e-6):
                    # 全零状态可能表示通信异常
                    if time.time() - last_state_time > timeout_threshold:
                        print("\n⚠️ 检测到状态异常（全零状态）")
                        print("   可能原因：通信中断或机器人未就绪")
                else:
                    last_state_time = time.time()

                # 检查关节角度是否超限（简单检查）
                if np.any(np.abs(q_pos) > 3.14):
                    print(f"\n⚠️ 检测到关节角度异常: {np.rad2deg(q_pos)}")

                time.sleep(check_interval)

            except Exception as e:
                print(f"\n⚠️ 状态监控错误: {e}")
                time.sleep(check_interval)

    def run(self):
        """运行监控器"""
        print("\n🚀 启动监控...")

        # 启动键盘监听线程
        keyboard_thread = threading.Thread(target=self.keyboard_monitor, daemon=True)
        keyboard_thread.start()

        # 启动状态监控线程
        state_thread = threading.Thread(target=self.state_monitor, daemon=True)
        state_thread.start()

        # 主线程等待
        try:
            while not self.stop_flag and not self.emergency_triggered:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")
            self.stop_flag = True

        # 确保发送停止命令
        if self.emergency_triggered:
            print("\n🛑 执行紧急停止...")
            self.send_stop_command()
            time.sleep(0.5)

        # 断开连接
        if self.driver is not None:
            self.driver.disconnect()

        print("\n✅ 监控器已退出")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="紧急停止监控器")
    parser.add_argument("--ip", type=str, default="192.168.1.183",
                        help="机器人控制器 IP 地址")
    parser.add_argument("--arm", type=str, default="right", choices=["left", "right"],
                        help="使用哪个手臂")

    args = parser.parse_args()

    # 创建监控器
    monitor = EmergencyStopMonitor(
        robot_ip=args.ip,
        arm_side=args.arm
    )

    # 连接真机
    monitor.connect()

    # 运行监控
    monitor.run()


if __name__ == "__main__":
    main()
