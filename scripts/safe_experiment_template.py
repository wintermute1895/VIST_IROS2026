#!/usr/bin/env python3
"""
VIST实验模板 - 集成所有安全功能
展示如何正确使用DataLogger、Watchdog和SafetyUtils
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import time
from src.config.config_loader import VISTConfig
from src.utils.data_logger import VISTDataLogger
from src.utils.robot_watchdog import RobotWatchdog, safe_control_loop
from src.utils.safety_utils import CommandSafetyMonitor, safe_clip_command


class MockRobotController:
    """模拟机器人控制器（用于演示）"""

    def __init__(self):
        self.is_stopped = False
        self.current_position = np.zeros(7)

    def stop(self):
        """紧急停止"""
        print("   [Robot] 🛑 发送零速度命令")
        self.is_stopped = True

    def send_command(self, command):
        """发送命令"""
        if not self.is_stopped:
            self.current_position += command * 0.01
            # print(f"   [Robot] 位置: {self.current_position[:3]}")

    def get_position(self):
        """获取当前位置"""
        return self.current_position.copy()


def run_safe_experiment():
    """
    运行安全的VIST实验

    这个函数展示了如何正确集成所有安全功能：
    1. 配置管理
    2. 数据记录（带配置快照）
    3. 安全看门狗（Ctrl+C保护）
    4. 命令限幅和异常检测
    """
    print("="*70)
    print("VIST安全实验模板")
    print("="*70)

    # 1. 加载配置
    print("\n[1/5] 加载配置...")
    config = VISTConfig()

    # 2. 创建数据记录器（自动保存配置快照）
    print("\n[2/5] 创建数据记录器...")
    logger = VISTDataLogger(
        experiment_name='safe_experiment_demo',
        config=config,
        metadata={
            'operator': 'Demo User',
            'condition': 'Simulation',
            'notes': '演示安全功能集成'
        }
    )

    # 3. 创建机器人控制器
    print("\n[3/5] 初始化机器人...")
    robot = MockRobotController()

    # 4. 创建安全监控器
    print("\n[4/5] 创建安全监控器...")
    joint_limits = config.robot_joint_limits
    safety_monitor = CommandSafetyMonitor(
        max_velocity=config.max_joint_velocity,
        max_acceleration=config.max_joint_acceleration,
        joint_limits=joint_limits
    )

    # 5. 运行安全控制循环
    print("\n[5/5] 开始实验...")
    print("提示: 按Ctrl+C可以安全停止实验\n")

    # 实验参数
    n_steps = 500
    dt = config.control_dt
    step_count = [0]  # 使用列表以便在闭包中修改

    def control_function():
        """控制函数（在安全循环中调用）"""
        i = step_count[0]
        step_count[0] += 1

        # 模拟时间
        timestamp = i * dt

        # 模拟人类输入（带噪声）
        human_input = np.sin(timestamp * 2 * np.pi * 0.5) * 0.5 + np.random.randn(7) * 0.1

        # 模拟VIST滤波输出
        filtered_output = human_input * 0.8  # 简化的滤波

        # 模拟意图因子
        alpha = min(1.0, timestamp / 5.0)  # 0到1的渐变

        # 模拟Q和R矩阵
        Q = np.eye(14) * (0.01 * (1 - alpha) + 0.001 * alpha)
        R = np.eye(7) * (0.01 * np.exp(3 * alpha))

        # 安全检查和限幅
        safe_command, is_safe = safety_monitor.check_and_clip(
            filtered_output,
            dt=dt,
            verbose=(i % 100 == 0)  # 每100步打印一次
        )

        # 发送命令到机器人
        robot.send_command(safe_command)

        # 记录数据
        logger.log_frame(
            timestamp=timestamp,
            human_input=human_input,
            filtered_output=safe_command,
            alpha=alpha,
            Q=Q,
            R=R
        )

        # 进度显示
        if i % 50 == 0:
            print(f"   进度: {i}/{n_steps} ({i/n_steps*100:.1f}%) | α={alpha:.3f}")

        # 继续运行
        return i < n_steps

    # 使用安全控制循环
    try:
        with RobotWatchdog(robot, heartbeat_timeout=5.0) as watchdog:
            while watchdog.is_running and step_count[0] < n_steps:
                if not control_function():
                    break
                watchdog.heartbeat()
                time.sleep(dt)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断")

    except Exception as e:
        print(f"\n❌ 异常: {e}")
        raise

    finally:
        # 确保机器人停止
        robot.stop()

        # 保存数据
        print("\n[保存数据]")
        logger.save(trial_number=1, notes="演示实验完成")

        # 打印统计信息
        print("\n[统计信息]")
        stats = safety_monitor.get_statistics()
        print(f"   安全违规次数: {stats['violation_count']}")
        print(f"   记录帧数: {logger.frame_count}")

        print("\n" + "="*70)
        print("✅ 实验完成！")
        print("="*70)

        # 打印数据位置
        summary = logger.get_summary()
        print(f"\n数据保存位置: {summary['exp_dir']}")
        print(f"实验ID: {summary['experiment_id']}")


def run_multiple_trials():
    """
    运行多次trial的示例

    展示如何使用同一个logger记录多次实验
    """
    print("="*70)
    print("多Trial实验示例")
    print("="*70)

    config = VISTConfig()
    logger = VISTDataLogger(
        experiment_name='multi_trial_demo',
        config=config
    )

    robot = MockRobotController()

    # 运行3次trial
    for trial in range(1, 4):
        print(f"\n{'='*70}")
        print(f"Trial {trial}/3")
        print(f"{'='*70}")

        # 模拟实验
        for i in range(100):
            timestamp = i * 0.01
            human_input = np.random.randn(7) * 0.5
            filtered_output = human_input * 0.8
            alpha = i / 100.0
            Q = np.eye(14) * 0.01
            R = np.eye(7) * 0.1

            logger.log_frame(timestamp, human_input, filtered_output, alpha, Q, R)

        # 保存这个trial
        logger.save(trial_number=trial, notes=f"Trial {trial} 完成")

        # 清空缓冲区，准备下一个trial
        logger.clear_buffer()

    print("\n" + "="*70)
    print("✅ 所有Trial完成！")
    print("="*70)

    summary = logger.get_summary()
    print(f"\n总共完成: {summary['trial_count']} 个trials")
    print(f"数据目录: {summary['exp_dir']}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='VIST安全实验模板')
    parser.add_argument('--mode', type=str, default='single',
                       choices=['single', 'multi'],
                       help='实验模式: single=单次实验, multi=多次trial')

    args = parser.parse_args()

    if args.mode == 'single':
        run_safe_experiment()
    elif args.mode == 'multi':
        run_multiple_trials()
