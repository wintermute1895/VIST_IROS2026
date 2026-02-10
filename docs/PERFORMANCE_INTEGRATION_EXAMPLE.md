# 性能监控集成示例

## 如何在主程序中集成性能监控

### 方法 1: 最小侵入式集成（推荐）

在 `run_real_robot_vist_refactored.py` 的 `run()` 方法中添加性能监控：

```python
# 在文件开头添加导入
from src.utils.performance_monitor import TeleopMetrics

class RealRobotVIST:
    def __init__(self, enable_visualization=None):
        # ... 现有代码 ...

        # 添加性能监控器
        self.perf_metrics = TeleopMetrics()

    def run(self, duration=None, countdown_seconds=10):
        # ... 现有代码 ...

        try:
            while time.time() - start_time < duration:
                # 开始计时总循环
                self.perf_metrics.monitor.start_timer("total_loop")
                loop_start = time.time()

                # 1. 接收人体关键点
                self.perf_metrics.monitor.start_timer("receive_keypoints")
                human_keypoints = self.robot.receive_keypoints()
                self.perf_metrics.monitor.stop_timer("receive_keypoints")

                if human_keypoints is None:
                    self.perf_metrics.monitor.stop_timer("total_loop")
                    time.sleep(self.config.control_dt)
                    continue

                # 2. VIST 控制器处理
                self.perf_metrics.monitor.start_timer("vist_process")
                q_safe, success, debug_info = self.controller.process(human_keypoints)
                self.perf_metrics.monitor.stop_timer("vist_process")

                if not success:
                    self.perf_metrics.record_failure()
                    self.perf_metrics.monitor.stop_timer("total_loop")
                    time.sleep(self.config.control_dt)
                    continue

                self.perf_metrics.record_success()
                success_count += 1

                # 3. 发送到真机
                self.perf_metrics.monitor.start_timer("send_command")
                self.robot.send_command(q_safe)
                self.perf_metrics.monitor.stop_timer("send_command")

                # 4. 记录跟踪误差（如果有）
                if 'tracking_error' in debug_info:
                    self.perf_metrics.record_tracking_error(debug_info['tracking_error'])

                # 5. 更新可视化
                if self.visualizer is not None and self.visualizer.enable:
                    self.visualizer.update(self.controller.q_current)

                frame_count += 1

                # 停止总循环计时
                self.perf_metrics.monitor.stop_timer("total_loop")

                # ... 现有的状态显示代码 ...

        except KeyboardInterrupt:
            print("\\n\\n⏹️ 用户中断")
        finally:
            # 断开连接
            self.robot.disconnect()

            # 打印性能摘要
            print("\\n" + "="*80)
            self.perf_metrics.print_summary()
            print("="*80)

            # 保存性能数据
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            self.perf_metrics.monitor.save_to_file(f"logs/performance_{timestamp}.json")

            # ... 现有的统计代码 ...
```

### 方法 2: 完整集成（详细版）

创建一个新的包装类：

```python
# scripts/run_real_robot_vist_with_perf.py
from run_real_robot_vist_refactored import RealRobotVIST
from src.utils.performance_monitor import TeleopMetrics
import time

class RealRobotVISTWithPerf(RealRobotVIST):
    """带性能监控的 VIST 真机控制"""

    def __init__(self, enable_visualization=None):
        super().__init__(enable_visualization)
        self.perf_metrics = TeleopMetrics()

    def run(self, duration=None, countdown_seconds=10):
        """运行真机控制循环（带性能监控）"""
        if duration is None:
            duration = self.config.control_duration

        # ... 倒计时代码 ...

        start_time = time.time()
        frame_count = 0
        success_count = 0
        last_print_time = time.time()

        try:
            while time.time() - start_time < duration:
                # 测量整个循环
                self.perf_metrics.monitor.start_timer("total_loop")
                loop_start = time.time()

                # 1. 接收关键点（测量）
                self.perf_metrics.monitor.start_timer("receive_keypoints")
                human_keypoints = self.robot.receive_keypoints()
                self.perf_metrics.monitor.stop_timer("receive_keypoints")

                if human_keypoints is None:
                    self.perf_metrics.monitor.stop_timer("total_loop")
                    time.sleep(self.config.control_dt)
                    continue

                # 2. VIST 处理（测量）
                self.perf_metrics.monitor.start_timer("vist_process")
                q_safe, success, debug_info = self.controller.process(human_keypoints)
                self.perf_metrics.monitor.stop_timer("vist_process")

                if not success:
                    self.perf_metrics.record_failure()
                    self.perf_metrics.monitor.stop_timer("total_loop")
                    time.sleep(self.config.control_dt)
                    continue

                self.perf_metrics.record_success()
                success_count += 1

                # 3. 发送命令（测量）
                self.perf_metrics.monitor.start_timer("send_command")
                self.robot.send_command(q_safe)
                self.perf_metrics.monitor.stop_timer("send_command")

                # 4. 记录跟踪误差
                if 'target_pos' in debug_info and 'current_pos' in debug_info:
                    import numpy as np
                    error = np.linalg.norm(
                        np.array(debug_info['target_pos']) -
                        np.array(debug_info['current_pos'])
                    )
                    self.perf_metrics.record_tracking_error(error)

                # 5. 更新可视化
                if self.visualizer is not None and self.visualizer.enable:
                    self.visualizer.update(self.controller.q_current)

                frame_count += 1
                self.perf_metrics.monitor.stop_timer("total_loop")

                # 6. 状态显示（每秒一次）
                if time.time() - last_print_time >= 1.0:
                    self._print_status(frame_count, success_count, debug_info)
                    last_print_time = time.time()

                # 控制频率
                elapsed = time.time() - loop_start
                if elapsed < self.config.control_dt:
                    time.sleep(self.config.control_dt - elapsed)

        except KeyboardInterrupt:
            print("\\n\\n⏹️ 用户中断")
        except Exception as e:
            print(f"\\n❌ 运行时错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._cleanup_and_report(start_time, frame_count, success_count)

    def _print_status(self, frame_count, success_count, debug_info):
        """打印状态信息"""
        success_rate = (success_count / frame_count * 100) if frame_count > 0 else 0
        status_msg = f"✅ 帧数: {frame_count} | 成功率: {success_rate:.1f}%"

        # 添加性能指标
        loop_stats = self.perf_metrics.monitor.get_stats("total_loop")
        if loop_stats:
            status_msg += f" | 延迟: {loop_stats['mean']*1000:.1f}ms"
            status_msg += f" | 频率: {loop_stats['frequency']:.1f}Hz"

        # VIST 意图因子
        if hasattr(self.controller.vist_filter, 'alpha_smoothed'):
            status_msg += f" | 意图: {self.controller.vist_filter.alpha_smoothed:.2f}"

        print(status_msg)

    def _cleanup_and_report(self, start_time, frame_count, success_count):
        """清理和报告"""
        # 断开连接
        self.robot.disconnect()

        # 打印详细性能报告
        print("\\n" + "="*80)
        print("📊 性能报告")
        print("="*80)

        # 基础统计
        print(f"\\n基础统计:")
        print(f"  总帧数: {frame_count}")
        print(f"  成功帧数: {success_count}")
        if frame_count > 0:
            print(f"  成功率: {success_count / frame_count * 100:.1f}%")
        print(f"  运行时长: {time.time() - start_time:.1f}秒")
        if frame_count > 0:
            print(f"  平均帧率: {frame_count / (time.time() - start_time):.1f} fps")

        # 性能详情
        self.perf_metrics.print_summary()

        # 保存性能数据
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"logs/performance_{timestamp}.json"
        self.perf_metrics.monitor.save_to_file(filename)

        # 安全控制器统计
        safety_stats = self.controller.get_safety_statistics()
        print(f"\\n🛡️  安全控制统计:")
        print(f"  速度限制: {safety_stats['velocity_limited_count']}次")
        print(f"  加速度限制: {safety_stats['acceleration_limited_count']}次")
        print(f"  位置限制: {safety_stats['position_limited_count']}次")

        # 关闭可视化器
        if self.visualizer is not None:
            self.visualizer.close()

        print("\\n✅ 真机控制器已退出")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="VIST 真机控制系统（带性能监控）")
    parser.add_argument("--duration", type=float, default=None,
                        help="运行时长（秒）")
    parser.add_argument("--countdown", type=int, default=10,
                        help="启动前倒计时（秒）")
    parser.add_argument("--viz", action="store_true",
                        help="启用可视化")
    parser.add_argument("--no-viz", action="store_true",
                        help="禁用可视化")

    args = parser.parse_args()

    # 确定是否启用可视化
    enable_viz = None
    if args.viz:
        enable_viz = True
    elif args.no_viz:
        enable_viz = False

    # 创建控制器
    controller = RealRobotVISTWithPerf(enable_visualization=enable_viz)

    # 连接真机
    controller.connect()

    # 运行控制循环
    controller.run(duration=args.duration, countdown_seconds=args.countdown)


if __name__ == "__main__":
    main()
```

## 使用方法

### 方法 1: 直接修改现有文件
1. 在 `run_real_robot_vist_refactored.py` 中添加性能监控代码
2. 运行: `python scripts/run_real_robot_vist_refactored.py`

### 方法 2: 创建新文件（推荐）
1. 创建 `scripts/run_real_robot_vist_with_perf.py`
2. 运行: `python scripts/run_real_robot_vist_with_perf.py`

## 输出示例

```
========================================
遥操作性能摘要
========================================

📊 receive_keypoints:
  样本数: 1000
  平均: 2.34 ms
  标准差: 0.56 ms
  最小: 1.23 ms
  最大: 8.45 ms
  中位数 (P50): 2.21 ms
  P95: 3.21 ms
  P99: 4.56 ms
  频率: 427.4 Hz

📊 vist_process:
  样本数: 950
  平均: 15.67 ms
  标准差: 2.34 ms
  最小: 12.34 ms
  最大: 25.67 ms
  中位数 (P50): 15.23 ms
  P95: 19.45 ms
  P99: 22.34 ms
  频率: 63.8 Hz

📊 send_command:
  样本数: 950
  平均: 1.23 ms
  标准差: 0.34 ms
  最小: 0.89 ms
  最大: 3.45 ms
  中位数 (P50): 1.18 ms
  P95: 1.78 ms
  P99: 2.34 ms
  频率: 813.0 Hz

📊 total_loop:
  样本数: 1000
  平均: 19.24 ms
  标准差: 2.89 ms
  最小: 15.67 ms
  最大: 32.45 ms
  中位数 (P50): 18.89 ms
  P95: 23.45 ms
  P99: 27.89 ms
  频率: 52.0 Hz
========================================

📈 遥操作指标:
  成功率: 95.0%
  成功次数: 950
  失败次数: 50

🎯 跟踪误差:
  平均: 2.34 mm
  标准差: 1.23 mm
  最大: 8.45 mm
========================================

✅ 性能数据已保存到: logs/performance_20260210_143052.json
```

## 性能数据分析

保存的 JSON 文件可以用于：
1. 论文实验数据
2. 性能对比（优化前后）
3. 系统瓶颈分析
4. 实时性验证

## 下一步

1. 选择集成方法（推荐方法 2）
2. 运行实验并收集数据
3. 分析性能瓶颈
4. 根据需要优化
