#!/usr/bin/env python3
"""
高频发布器 - 将低频控制指令插值到高频输出

功能：
1. 主循环以低频（20-30Hz）计算控制指令
2. 发布线程以高频（250Hz）插值发布
3. 使用线性插值或样条插值平滑过渡

用途：
- 让视觉控制（30Hz）能够以250Hz发布
- 与遥操臂（241.75Hz）频率匹配
- 保持控制平滑性
"""

import threading
import time
import numpy as np
from scipy.interpolate import interp1d


class HighFrequencyPublisher:
    """
    高频发布器

    原理：
    - 主线程：低频更新目标位置（20-30Hz）
    - 发布线程：高频插值发布（250Hz）
    - 插值方法：线性或三次样条
    """

    def __init__(self, ros2_publisher, target_freq=250.0, interpolation='linear'):
        """
        初始化高频发布器

        Args:
            ros2_publisher: ROS2发布器实例
            target_freq: 目标发布频率 (Hz)
            interpolation: 插值方法 ('linear' 或 'cubic')
        """
        self.ros2_publisher = ros2_publisher
        self.target_freq = target_freq
        self.dt = 1.0 / target_freq
        self.interpolation = interpolation

        # 状态变量
        self.q_current = None  # 当前位置
        self.q_target = None   # 目标位置
        self.q_history = []    # 历史位置（用于样条插值）
        self.t_history = []    # 历史时间戳

        # 线程控制
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

        # 统计信息
        self.publish_count = 0
        self.update_count = 0
        self.start_time = None

        print(f"✅ 高频发布器初始化完成")
        print(f"   目标频率: {target_freq} Hz")
        print(f"   插值方法: {interpolation}")

    def start(self, q_init=None):
        """
        启动发布线程

        Args:
            q_init: 初始关节角度
        """
        if q_init is not None:
            with self.lock:
                self.q_current = np.array(q_init, dtype=float)
                self.q_target = np.array(q_init, dtype=float)

        self.running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._publish_loop, daemon=True)
        self.thread.start()
        print("✅ 高频发布线程已启动")

    def update_target(self, q_target):
        """
        更新目标位置（由主循环调用）

        Args:
            q_target: 新的目标关节角度
        """
        with self.lock:
            self.q_target = np.array(q_target, dtype=float)
            self.update_count += 1

            # 记录历史（用于样条插值）
            current_time = time.time() - self.start_time if self.start_time else 0
            self.t_history.append(current_time)
            self.q_history.append(self.q_target.copy())

            # 只保留最近的10个点
            if len(self.q_history) > 10:
                self.t_history.pop(0)
                self.q_history.pop(0)

    def _publish_loop(self):
        """发布循环（在独立线程中运行）"""
        while self.running:
            loop_start = time.time()

            with self.lock:
                if self.q_target is not None:
                    # 初始化
                    if self.q_current is None:
                        self.q_current = self.q_target.copy()
                    else:
                        # 插值到目标
                        if self.interpolation == 'linear':
                            # 线性插值（简单快速）
                            alpha = 0.2  # 平滑因子（越小越平滑，但延迟越大）
                            self.q_current = (1 - alpha) * self.q_current + alpha * self.q_target

                        elif self.interpolation == 'cubic' and len(self.q_history) >= 4:
                            # 三次样条插值（更平滑）
                            try:
                                current_time = time.time() - self.start_time
                                # 为每个关节创建插值器
                                q_interp = np.zeros(len(self.q_current))
                                for i in range(len(self.q_current)):
                                    joint_history = [q[i] for q in self.q_history]
                                    interpolator = interp1d(
                                        self.t_history,
                                        joint_history,
                                        kind='cubic',
                                        fill_value='extrapolate'
                                    )
                                    q_interp[i] = interpolator(current_time)
                                self.q_current = q_interp
                            except Exception as e:
                                # 如果插值失败，回退到线性插值
                                alpha = 0.2
                                self.q_current = (1 - alpha) * self.q_current + alpha * self.q_target

                    # 发布
                    self.ros2_publisher.publish(self.q_current)
                    self.publish_count += 1

            # 控制频率
            elapsed = time.time() - loop_start
            sleep_time = max(0, self.dt - elapsed)
            time.sleep(sleep_time)

    def stop(self):
        """停止发布线程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)

        # 打印统计信息
        if self.start_time:
            duration = time.time() - self.start_time
            actual_pub_freq = self.publish_count / duration if duration > 0 else 0
            actual_update_freq = self.update_count / duration if duration > 0 else 0

            print(f"\n高频发布器统计:")
            print(f"  运行时间: {duration:.2f}秒")
            print(f"  发布次数: {self.publish_count}")
            print(f"  更新次数: {self.update_count}")
            print(f"  实际发布频率: {actual_pub_freq:.2f} Hz")
            print(f"  实际更新频率: {actual_update_freq:.2f} Hz")

    def get_stats(self):
        """获取统计信息"""
        if self.start_time:
            duration = time.time() - self.start_time
            return {
                'duration': duration,
                'publish_count': self.publish_count,
                'update_count': self.update_count,
                'publish_freq': self.publish_count / duration if duration > 0 else 0,
                'update_freq': self.update_count / duration if duration > 0 else 0
            }
        return None


# ============================================
# 使用示例
# ============================================

def example_usage():
    """
    在 simulate_full_flow.py 中的使用示例

    # 1. 在 __init__ 中初始化
    from scripts.high_frequency_publisher import HighFrequencyPublisher

    # 创建高频发布器
    self.high_freq_pub = HighFrequencyPublisher(
        ros2_publisher=self.ros2_publisher,
        target_freq=250.0,
        interpolation='linear'  # 或 'cubic'
    )

    # 2. 在主循环开始前启动
    # 启动高频发布
    self.high_freq_pub.start(q_init=self.q_current)

    # 3. 在主循环中更新目标（20-30Hz）
    # 计算新的关节角度
    q_solution = self.solver.solve(...)

    # 更新高频发布器的目标
    self.high_freq_pub.update_target(q_solution)

    # 不需要直接发布，高频发布器会自动以250Hz发布

    # 4. 退出时停止
    self.high_freq_pub.stop()
    """
    pass


if __name__ == '__main__':
    # 测试高频发布器
    print("测试高频发布器...")

    # 模拟ROS2发布器
    class MockPublisher:
        def __init__(self):
            self.count = 0

        def publish(self, data):
            self.count += 1
            if self.count % 50 == 0:  # 每50次打印一次
                print(f"发布第 {self.count} 条数据: {data[:3]}...")

    mock_pub = MockPublisher()

    # 创建高频发布器
    high_freq_pub = HighFrequencyPublisher(
        ros2_publisher=mock_pub,
        target_freq=250.0,
        interpolation='linear'
    )

    # 启动
    q_init = np.zeros(7)
    high_freq_pub.start(q_init)

    # 模拟主循环以20Hz更新目标
    print("\n模拟主循环（20Hz更新目标）...")
    for i in range(20):  # 运行1秒
        # 生成新的目标位置
        q_target = np.sin(i * 0.1) * np.ones(7)
        high_freq_pub.update_target(q_target)
        time.sleep(0.05)  # 20Hz

    # 停止
    high_freq_pub.stop()

    print("\n测试完成")
    print(f"模拟发布器收到 {mock_pub.count} 条消息")