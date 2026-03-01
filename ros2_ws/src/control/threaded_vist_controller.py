"""
多线程 VIST 控制器
使用成熟的工业方案实现4线程架构，优化控制频率

线程架构：
- Vision Thread (30Hz): UDP 接收人体关键点数据
- Control Thread (100Hz): VIST 处理 + 机器人命令发送
- Visualization Thread (10Hz): 可视化渲染
- Stats Thread (1Hz): 性能监控

通信方案：
- 线程间通信：collections.deque(maxlen=1) + threading.Lock
- 数据序列化：MessagePack（比 JSON 快 5-10 倍）
- 包丢失检测：seq + timestamp

创建日期：2026-02-18
"""

import threading
import time
import numpy as np
from collections import deque
from typing import Optional, Dict, Any
import traceback

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ThreadSafeQueue:
    """线程安全的单元素队列（只保留最新数据）

    使用 deque(maxlen=1) + Lock 实现
    这是工业标准的 Producer-Consumer 模式
    """

    def __init__(self):
        self._queue = deque(maxlen=1)
        self._lock = threading.Lock()

    def put(self, item):
        """放入数据（自动覆盖旧数据）"""
        with self._lock:
            self._queue.append(item)

    def get(self) -> Optional[Any]:
        """获取数据（非阻塞）"""
        with self._lock:
            if len(self._queue) > 0:
                return self._queue[0]
            return None

    def clear(self):
        """清空队列"""
        with self._lock:
            self._queue.clear()


class PerformanceMonitor:
    """性能监控器

    监控各线程的实际运行频率和延迟
    """

    def __init__(self):
        self._counters = {}
        self._last_print_time = time.time()
        self._lock = threading.Lock()

    def tick(self, thread_name: str):
        """记录一次执行"""
        with self._lock:
            if thread_name not in self._counters:
                self._counters[thread_name] = {
                    'count': 0,
                    'start_time': time.time()
                }
            self._counters[thread_name]['count'] += 1

    def get_stats(self) -> Dict[str, float]:
        """获取统计信息（Hz）"""
        with self._lock:
            current_time = time.time()
            stats = {}
            for name, data in self._counters.items():
                elapsed = current_time - data['start_time']
                if elapsed > 0:
                    stats[name] = data['count'] / elapsed
            return stats

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        logger.info("=== 线程性能统计 ===")
        for name, freq in stats.items():
            logger.info(f"  {name}: {freq:.1f} Hz")


class ThreadedVISTController:
    """多线程 VIST 控制器

    封装 VISTController，使用 4 线程架构提升控制频率
    """

    def __init__(self, vist_controller, robot_interface, udp_receiver, visualizer=None):
        """
        初始化多线程控制器

        Args:
            vist_controller: VISTController 实例
            robot_interface: RobotInterface 实例
            udp_receiver: UDPReceiver 实例
            visualizer: Visualizer 实例（可选）
        """
        self.vist_controller = vist_controller
        self.robot_interface = robot_interface
        self.udp_receiver = udp_receiver
        self.visualizer = visualizer

        # 线程间通信队列
        self.vision_queue = ThreadSafeQueue()  # Vision -> Control
        self.viz_queue = ThreadSafeQueue()    # Control -> Visualization

        # 性能监控
        self.perf_monitor = PerformanceMonitor()

        # 线程控制
        self._running = False
        self._threads = []

        # 统计信息
        self._stats = {
            'vision_packets_received': 0,
            'control_commands_sent': 0,
            'control_failures': 0,
            'viz_frames_rendered': 0
        }
        self._stats_lock = threading.Lock()

        logger.info("多线程 VIST 控制器初始化完成")
        logger.info("线程架构: Vision(30Hz) + Control(100Hz) + Viz(10Hz) + Stats(1Hz)")

    def start(self):
        """启动所有线程"""
        if self._running:
            logger.warning("控制器已在运行")
            return

        self._running = True

        # 创建并启动线程
        self._threads = [
            threading.Thread(target=self._vision_thread, name="VisionThread", daemon=True),
            threading.Thread(target=self._control_thread, name="ControlThread", daemon=True),
            threading.Thread(target=self._visualization_thread, name="VisualizationThread", daemon=True),
            threading.Thread(target=self._stats_thread, name="StatsThread", daemon=True)
        ]

        for thread in self._threads:
            thread.start()
            logger.info(f"启动线程: {thread.name}")

        logger.info("所有线程已启动")

    def stop(self):
        """停止所有线程"""
        if not self._running:
            return

        logger.info("正在停止所有线程...")
        self._running = False

        # 等待所有线程结束
        for thread in self._threads:
            thread.join(timeout=2.0)
            if thread.is_alive():
                logger.warning(f"线程 {thread.name} 未能正常结束")

        logger.info("所有线程已停止")

    def _vision_thread(self):
        """Vision Thread: 接收 UDP 数据 (30Hz)"""
        target_freq = 30  # Hz
        period = 1.0 / target_freq

        logger.info(f"Vision Thread 启动 (目标频率: {target_freq} Hz)")

        while self._running:
            loop_start = time.time()

            try:
                # 接收 UDP 数据
                data = self.udp_receiver.receive()

                if data is not None:
                    # 放入队列供 Control Thread 使用
                    self.vision_queue.put(data)

                    with self._stats_lock:
                        self._stats['vision_packets_received'] += 1

                    self.perf_monitor.tick('Vision')

            except Exception as e:
                logger.error(f"Vision Thread 错误: {e}")
                logger.debug(traceback.format_exc())

            # 频率控制
            elapsed = time.time() - loop_start
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Vision Thread 已停止")

    def _control_thread(self):
        """Control Thread: VIST 处理 + 命令发送 (100Hz)"""
        target_freq = 100  # Hz
        period = 1.0 / target_freq

        logger.info(f"Control Thread 启动 (目标频率: {target_freq} Hz)")

        while self._running:
            loop_start = time.time()

            try:
                # 从队列获取最新数据
                vision_data = self.vision_queue.get()

                if vision_data is not None:
                    # VIST 处理
                    human_keypoints = vision_data.get('keypoints')
                    camera_image = vision_data.get('image')

                    if human_keypoints is not None:
                        q_safe, success, debug_info = self.vist_controller.process(
                            human_keypoints,
                            camera_image
                        )

                        if success and q_safe is not None:
                            # 发送命令到机器人
                            self.robot_interface.send_command(q_safe)

                            with self._stats_lock:
                                self._stats['control_commands_sent'] += 1

                            # 准备可视化数据
                            viz_data = {
                                'q_safe': q_safe,
                                'debug_info': debug_info,
                                'timestamp': time.time()
                            }
                            self.viz_queue.put(viz_data)
                        else:
                            # IK 失败降级策略：发送停止指令（保持当前位置）
                            try:
                                _, q_current, _ = self.robot_interface.get_state()
                                self.robot_interface.send_command(q_current)
                                logger.warning("VIST 求解失败，发送停止指令（保持当前位置）")
                            except Exception as e:
                                logger.error(f"发送停止指令失败: {e}")

                            with self._stats_lock:
                                self._stats['control_failures'] += 1

                    self.perf_monitor.tick('Control')

            except Exception as e:
                logger.error(f"Control Thread 错误: {e}")
                logger.debug(traceback.format_exc())
                with self._stats_lock:
                    self._stats['control_failures'] += 1

            # 频率控制
            elapsed = time.time() - loop_start
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Control Thread 已停止")

    def _visualization_thread(self):
        """Visualization Thread: 渲染可视化 (10Hz)"""
        if self.visualizer is None:
            logger.info("Visualization Thread 未启动（无可视化器）")
            return

        target_freq = 10  # Hz
        period = 1.0 / target_freq

        logger.info(f"Visualization Thread 启动 (目标频率: {target_freq} Hz)")

        while self._running:
            loop_start = time.time()

            try:
                # 从队列获取可视化数据
                viz_data = self.viz_queue.get()

                if viz_data is not None:
                    # 渲染
                    self.visualizer.render(viz_data)

                    with self._stats_lock:
                        self._stats['viz_frames_rendered'] += 1

                    self.perf_monitor.tick('Visualization')

            except Exception as e:
                logger.error(f"Visualization Thread 错误: {e}")
                logger.debug(traceback.format_exc())

            # 频率控制
            elapsed = time.time() - loop_start
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Visualization Thread 已停止")

    def _stats_thread(self):
        """Stats Thread: 性能监控 (1Hz)"""
        target_freq = 1  # Hz
        period = 1.0 / target_freq

        logger.info(f"Stats Thread 启动 (目标频率: {target_freq} Hz)")

        while self._running:
            loop_start = time.time()

            try:
                # 打印性能统计
                self.perf_monitor.print_stats()

                # 打印业务统计
                with self._stats_lock:
                    logger.info("=== 业务统计 ===")
                    logger.info(f"  Vision 接收: {self._stats['vision_packets_received']} 包")
                    logger.info(f"  Control 发送: {self._stats['control_commands_sent']} 命令")
                    logger.info(f"  Control 失败: {self._stats['control_failures']} 次")
                    logger.info(f"  Viz 渲染: {self._stats['viz_frames_rendered']} 帧")

                self.perf_monitor.tick('Stats')

            except Exception as e:
                logger.error(f"Stats Thread 错误: {e}")
                logger.debug(traceback.format_exc())

            # 频率控制
            elapsed = time.time() - loop_start
            sleep_time = period - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        logger.info("Stats Thread 已停止")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._stats_lock:
            stats = self._stats.copy()

        stats['thread_frequencies'] = self.perf_monitor.get_stats()
        return stats

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self._running