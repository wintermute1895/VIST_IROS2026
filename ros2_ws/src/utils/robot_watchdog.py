"""
机器人安全看门狗 - 防止失控
确保Ctrl+C和异常情况下机器人安全停止
"""

import signal
import sys
import time
import numpy as np
from typing import Callable, Optional, Any


class RobotWatchdog:
    """
    机器人安全看门狗

    功能：
    1. 捕获Ctrl+C (SIGINT)信号
    2. 捕获终止(SIGTERM)信号
    3. 确保机器人在任何情况下都能安全停止
    4. 提供心跳检测（可选）
    """

    def __init__(
        self,
        robot_controller: Any,
        stop_method: str = 'stop',
        heartbeat_timeout: Optional[float] = None
    ):
        """
        初始化看门狗

        Args:
            robot_controller: 机器人控制器对象
            stop_method: 停止方法名称（默认'stop'）
            heartbeat_timeout: 心跳超时时间（秒），None表示不启用
        """
        self.robot = robot_controller
        self.stop_method = stop_method
        self.is_running = True
        self.emergency_stop_triggered = False

        # 心跳检测
        self.heartbeat_timeout = heartbeat_timeout
        self.last_heartbeat = time.time()

        # 注册信号处理器
        signal.signal(signal.SIGINT, self._emergency_stop_handler)
        signal.signal(signal.SIGTERM, self._emergency_stop_handler)

        print("🛡️ [Watchdog] 安全看门狗已启动")
        print(f"   停止方法: {stop_method}")
        if heartbeat_timeout:
            print(f"   心跳超时: {heartbeat_timeout}s")

    def _emergency_stop_handler(self, signum, frame):
        """紧急停止处理器（信号处理）"""
        if self.emergency_stop_triggered:
            # 如果已经触发过，直接强制退出
            print("\n🚨 [WATCHDOG] 强制退出！")
            sys.exit(1)

        print("\n🚨 [WATCHDOG] 检测到中断信号，紧急停止机器人！")
        self.emergency_stop_triggered = True
        self.is_running = False

        # 调用机器人停止方法
        try:
            stop_func = getattr(self.robot, self.stop_method)
            stop_func()
            print("✅ [WATCHDOG] 机器人已安全停止")
        except Exception as e:
            print(f"❌ [WATCHDOG] 停止失败: {e}")

        sys.exit(0)

    def heartbeat(self):
        """更新心跳（在控制循环中调用）"""
        self.last_heartbeat = time.time()

    def check_heartbeat(self) -> bool:
        """
        检查心跳是否超时

        Returns:
            True if OK, False if timeout
        """
        if self.heartbeat_timeout is None:
            return True

        elapsed = time.time() - self.last_heartbeat
        if elapsed > self.heartbeat_timeout:
            print(f"⚠️ [WATCHDOG] 心跳超时！({elapsed:.2f}s > {self.heartbeat_timeout}s)")
            return False

        return True

    def __enter__(self):
        """支持with语句"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出时确保机器人停止"""
        if not self.emergency_stop_triggered:
            print("🛑 [WATCHDOG] 退出时确保机器人停止...")
            try:
                stop_func = getattr(self.robot, self.stop_method)
                stop_func()
                print("✅ [WATCHDOG] 机器人已安全停止")
            except Exception as e:
                print(f"❌ [WATCHDOG] 停止失败: {e}")


def safe_control_loop(
    robot_controller: Any,
    control_function: Callable,
    max_iterations: Optional[int] = None,
    heartbeat_timeout: float = 5.0
):
    """
    安全的控制循环包装器

    Args:
        robot_controller: 机器人控制器
        control_function: 控制函数，返回False时退出循环
        max_iterations: 最大迭代次数（None表示无限）
        heartbeat_timeout: 心跳超时时间

    Example:
        def my_control():
            command = compute_command()
            robot.send_command(command)
            return True  # 继续运行

        safe_control_loop(robot, my_control, max_iterations=1000)
    """
    with RobotWatchdog(robot_controller, heartbeat_timeout=heartbeat_timeout) as watchdog:
        iteration = 0

        try:
            while watchdog.is_running:
                # 检查迭代次数
                if max_iterations and iteration >= max_iterations:
                    print(f"✅ [Control] 达到最大迭代次数: {max_iterations}")
                    break

                # 执行控制函数
                should_continue = control_function()

                if not should_continue:
                    print("✅ [Control] 控制函数请求退出")
                    break

                # 更新心跳
                watchdog.heartbeat()

                # 检查心跳
                if not watchdog.check_heartbeat():
                    print("🚨 [Control] 心跳超时，紧急停止！")
                    break

                iteration += 1

        except Exception as e:
            print(f"🚨 [Control] 异常: {e}")
            raise

        finally:
            print(f"🛑 [Control] 控制循环结束（迭代: {iteration}）")


# 使用示例
if __name__ == '__main__':
    print("="*60)
    print("RobotWatchdog 使用示例")
    print("="*60)

    # 模拟机器人控制器
    class MockRobot:
        def __init__(self):
            self.is_stopped = False

        def stop(self):
            print("   [Robot] 发送零速度命令...")
            self.is_stopped = True

        def send_command(self, command):
            if not self.is_stopped:
                print(f"   [Robot] 发送命令: {command[:3]}...")

    robot = MockRobot()

    # 方法1: 使用with语句
    print("\n方法1: 使用with语句")
    print("按Ctrl+C测试紧急停止...")

    try:
        with RobotWatchdog(robot) as watchdog:
            for i in range(10):
                if not watchdog.is_running:
                    break

                command = np.random.randn(7)
                robot.send_command(command)
                watchdog.heartbeat()

                time.sleep(0.1)

    except KeyboardInterrupt:
        print("捕获到KeyboardInterrupt")

    print("\n方法2: 使用safe_control_loop")

    robot2 = MockRobot()
    iteration_count = [0]

    def my_control_function():
        iteration_count[0] += 1
        command = np.random.randn(7)
        robot2.send_command(command)
        time.sleep(0.1)
        return iteration_count[0] < 10  # 运行10次后退出

    safe_control_loop(robot2, my_control_function, max_iterations=10)

    print("\n" + "="*60)
    print("✅ 示例完成！")
    print("="*60)
