#!/usr/bin/env python3
"""
VIST 真机控制主程序（重构版）
完整集成 VIST 框架到真机，采用模块化架构

核心组件：
1. VISTController - VIST 算法控制器（纯算法逻辑）
2. RobotInterface - 机器人接口（硬件交互）
3. RobotVisualizer - 可视化器（可选）

Author: VIST Project
Date: 2026-02-07
"""

import os
import sys
import time

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.config import get_config
from src.control.vist_controller import VISTController
from src.robot.robot_interface import RobotInterface
from src.robot.visualizer import RobotVisualizer


class RealRobotVIST:
    """VIST 真机控制主程序（协调器）"""

    def __init__(self, enable_visualization=None):
        """
        初始化真机控制器

        Args:
            enable_visualization: 是否启用可视化（None=从配置读取）
        """
        print("=" * 80)
        print("🦾 VIST 真机控制系统（重构版）")
        print("=" * 80)

        # 1. 加载配置
        print("\n📁 加载系统配置...")
        self.config = get_config()
        print("✅ 配置加载完成")

        # 2. 初始化 VIST 控制器（算法层）
        self.controller = VISTController(self.config)

        # 3. 初始化机器人接口（硬件层）
        self.robot = RobotInterface(self.config)

        # 4. 初始化可视化器（可选）
        if enable_visualization is None:
            enable_visualization = self.config.visualization_enable

        self.visualizer = None
        if enable_visualization:
            print("\n🎨 初始化可视化器...")
            try:
                self.visualizer = RobotVisualizer(
                    model=self.controller.ik_solver.model,
                    collision_model=self.controller.ik_solver.collision_model,
                    visual_model=self.controller.ik_solver.visual_model,
                    enable=True
                )
                if self.visualizer.enable:
                    print(f"✅ 可视化器初始化成功: {self.visualizer.get_url()}")
            except Exception as e:
                print(f"⚠️ 可视化器初始化失败: {e}")
                self.visualizer = None

        print("\n✅ 初始化完成！")
        print("\n" + "=" * 80)

    def connect(self):
        """连接到真机"""
        q_init = self.robot.connect()

        # 初始化控制器的当前状态
        import pinocchio as pin
        import numpy as np
        q_full = pin.neutral(self.controller.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.controller.ik_solver.controlled_indices):
            if i < len(q_init) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_init[i]
        self.controller.q_current = q_full

        # 初始化安全控制器的当前状态
        self.controller.safety_controller.q_current = q_init.copy()

    def run(self, duration=None, countdown_seconds=10):
        """
        运行真机控制循环

        Args:
            duration: 运行时长（秒），None=从配置读取
            countdown_seconds: 启动前倒计时（秒）
        """
        if duration is None:
            duration = self.config.control_duration

        print("\n" + "=" * 80)
        print("🚀 准备启动真机控制...")
        print("=" * 80)

        print("\n⚠️  安全提示：")
        print("   1. 确保机器人周围无障碍物")
        print("   2. 确保紧急停止按钮可用")
        print("   3. 确保视觉节点正在运行")
        print("   4. 按 Ctrl+C 可随时停止")

        # 倒计时
        print(f"\n⏱️  {countdown_seconds}秒后开始...")
        for i in range(countdown_seconds, 0, -1):
            print(f"   {i}...", end='\r')
            time.sleep(1)
        print("   🚀 开始！" + " " * 20)

        start_time = time.time()
        frame_count = 0
        success_count = 0
        last_print_time = time.time()

        try:
            while time.time() - start_time < duration:
                loop_start = time.time()

                # 1. 接收人体关键点
                human_keypoints = self.robot.receive_keypoints()
                if human_keypoints is None:
                    time.sleep(self.config.control_dt)
                    continue

                # 检查关键点是否完整
                if 'wrist' not in human_keypoints or 'elbow' not in human_keypoints:
                    time.sleep(self.config.control_dt)
                    continue

                # 2. VIST 控制器处理
                q_safe, success, debug_info = self.controller.process(human_keypoints)

                if not success:
                    # 处理失败，跳过此帧
                    if frame_count % 30 == 0:
                        print(f"\n⚠️ 控制失败: {debug_info.get('error', 'Unknown')}")
                    time.sleep(self.config.control_dt)
                    continue

                success_count += 1

                # 3. 发送到真机
                self.robot.send_command(q_safe)

                # 4. 更新可视化
                if self.visualizer is not None and self.visualizer.enable:
                    self.visualizer.update(self.controller.q_current)

                frame_count += 1

                # 5. 状态显示（每秒一次）
                if time.sleep() - last_print_time >= 1.0:
                    success_rate = (success_count / frame_count * 100) if frame_count > 0 else 0

                    status_msg = f"✅ 帧数: {frame_count} | 成功率: {success_rate:.1f}%"

                    # VIST 意图因子
                    if hasattr(self.controller.vist_filter, 'alpha_smoothed'):
                        status_msg += f" | 意图: {self.controller.vist_filter.alpha_smoothed:.2f}"

                    # 安全状态
                    safety_status = debug_info.get('safety_status', {})
                    if any([safety_status.get('velocity_limited'),
                            safety_status.get('acceleration_limited'),
                            safety_status.get('position_limited')]):
                        status_msg += " | 安全限制"

                    # 目标位置
                    if 'target_pos' in debug_info:
                        target_pos = debug_info['target_pos']
                        status_msg += f" | 目标: [{target_pos[0]:.2f}, {target_pos[1]:.2f}, {target_pos[2]:.2f}]"

                    print(status_msg)
                    last_print_time = time.time()

                # 控制频率
                elapsed = time.time() - loop_start
                if elapsed < self.config.control_dt:
                    time.sleep(self.config.control_dt - elapsed)

        except KeyboardInterrupt:
            print("\n\n⏹️ 用户中断")
        except Exception as e:
            print(f"\n❌ 运行时错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 断开连接
            self.robot.disconnect()

            # 统计信息
            print(f"\n📊 统计:")
            print(f"   总帧数: {frame_count}")
            print(f"   成功帧数: {success_count}")
            if frame_count > 0:
                print(f"   成功率: {success_count / frame_count * 100:.1f}%")
            print(f"   运行时长: {time.time() - start_time:.1f}秒")
            if frame_count > 0:
                print(f"   平均帧率: {frame_count / (time.time() - start_time):.1f} fps")

            # 安全控制器统计
            safety_stats = self.controller.get_safety_statistics()
            print(f"\n🛡️  安全控制统计:")
            print(f"   速度限制: {safety_stats['velocity_limited_count']}次")
            print(f"   加速度限制: {safety_stats['acceleration_limited_count']}次")
            print(f"   位置限制: {safety_stats['position_limited_count']}次")

            # 关闭可视化器
            if self.visualizer is not None:
                self.visualizer.close()

            print("\n✅ 真机控制器已退出")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="VIST 真机控制系统（重构版）")
    parser.add_argument("--duration", type=float, default=None,
                        help="运行时长（秒），默认从配置读取")
    parser.add_argument("--countdown", type=int, default=10,
                        help="启动前倒计时（秒）")
    parser.add_argument("--viz", action="store_true",
                        help="启用 MeshCat 可视化")
    parser.add_argument("--no-viz", action="store_true",
                        help="禁用 MeshCat 可视化")

    args = parser.parse_args()

    # 确定是否启用可视化
    enable_viz = None
    if args.viz:
        enable_viz = True
    elif args.no_viz:
        enable_viz = False

    # 创建控制器
    controller = RealRobotVIST(enable_visualization=enable_viz)

    # 连接真机
    controller.connect()

    # 运行控制循环
    controller.run(
        duration=args.duration,
        countdown_seconds=args.countdown
    )


if __name__ == "__main__":
    main()
