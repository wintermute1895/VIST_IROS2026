#!/usr/bin/env python3
"""
为 simulate_full_flow.py 添加高频插值和简单滤波的补丁

使用方法：
1. 备份原文件: cp scripts/experiments/simulate_full_flow.py scripts/experiments/simulate_full_flow.py.bak
2. 应用此补丁中的修改
"""

# ============================================
# 修改1: 在文件开头添加导入（第38行之后）
# ============================================

IMPORT_ADDITION = """
from src.control.trajectory_interpolator import TrajectoryInterpolator
from src.utils.data_logger import VISTDataLogger
from src.utils.performance_monitor import TeleopMetrics

# 添加以下导入 ↓
import sys
sys.path.insert(0, os.path.join(project_root, 'scripts'))
from simulation_ros2_publisher import SimulationPublisherWrapper
from high_frequency_publisher import HighFrequencyPublisher
"""

# ============================================
# 修改2: 在 __init__ 方法末尾添加（约第240行）
# ============================================

INIT_ADDITION = """
        print("\\n✅ 初始化完成！")
        print("\\n" + "=" * 80)

        # 添加以下代码 ↓
        # 9. 初始化ROS2发布器和高频插值
        print("\\n📡 初始化ROS2高频发布系统...")

        # 9.1 创建基础ROS2发布器
        enable_ros2 = getattr(self.config, 'simulation_enable_ros2_publish', True)
        publish_rate = getattr(self.config, 'vision_fps', 30.0)

        self.ros2_publisher = SimulationPublisherWrapper(
            publish_rate=publish_rate,
            enable_ros2=enable_ros2
        )

        # 9.2 创建高频发布器（250Hz）
        if enable_ros2 and self.ros2_publisher.node is not None:
            target_freq = 250.0  # 目标频率
            interpolation = 'linear'  # 简单线性插值

            self.high_freq_pub = HighFrequencyPublisher(
                ros2_publisher=self.ros2_publisher,
                target_freq=target_freq,
                interpolation=interpolation
            )
            print(f"✅ 高频发布系统初始化完成")
            print(f"   主循环频率: {publish_rate} Hz")
            print(f"   发布频率: {target_freq} Hz")
            print(f"   插值方法: {interpolation}")
        else:
            self.high_freq_pub = None
            print("⚠️  ROS2发布已禁用，跳过高频发布器")

        # 9.3 初始化简单滤波器（EMA - 指数移动平均）
        self.enable_simple_filter = getattr(self.config, 'enable_simple_filter', True)
        if self.enable_simple_filter:
            self.filter_alpha = getattr(self.config, 'simple_filter_alpha', 0.3)
            self.q_filtered = None
            print(f"✅ 简单滤波器已启用 (EMA, α={self.filter_alpha})")
        else:
            print("⚠️  简单滤波器已禁用")
"""

# ============================================
# 修改3: 在 run() 方法开始处添加（约第400行）
# ============================================

RUN_START_ADDITION = """
    def run(self):
        \"\"\"主循环\"\"\"
        try:
            # 添加以下代码 ↓
            # 启动高频发布器
            if hasattr(self, 'high_freq_pub') and self.high_freq_pub is not None:
                init_q = self.q_current[self.ik_solver.controlled_indices]
                self.high_freq_pub.start(q_init=init_q)
                print("✅ 高频发布器已启动")

            # 原有代码继续...
"""

# ============================================
# 修改4: 在主循环中IK求解后添加（约第650行）
# ============================================

MAIN_LOOP_ADDITION = """
                                # IK求解完成，得到 q_solution

                                # 添加以下代码 ↓
                                # 4.1 应用简单滤波（可选）
                                if hasattr(self, 'enable_simple_filter') and self.enable_simple_filter:
                                    if self.q_filtered is None:
                                        self.q_filtered = q_solution.copy()
                                    else:
                                        # EMA滤波: q_filtered = α * q_new + (1-α) * q_old
                                        self.q_filtered = (self.filter_alpha * q_solution +
                                                          (1 - self.filter_alpha) * self.q_filtered)
                                    q_to_publish = self.q_filtered
                                else:
                                    q_to_publish = q_solution

                                # 4.2 更新高频发布器（250Hz插值发布）
                                if hasattr(self, 'high_freq_pub') and self.high_freq_pub is not None:
                                    self.high_freq_pub.update_target(q_to_publish)

                                # 原有的插值和安全控制代码继续...
                                if hasattr(self, 'interpolator'):
"""

# ============================================
# 修改5: 在 finally 块中添加清理（约第750行）
# ============================================

FINALLY_ADDITION = """
        finally:
            # 添加以下代码 ↓
            # 清理高频发布器
            if hasattr(self, 'high_freq_pub') and self.high_freq_pub is not None:
                print("\\n🔌 停止高频发布器...")
                self.high_freq_pub.stop()

            # 清理ROS2发布器
            if hasattr(self, 'ros2_publisher'):
                print("🔌 关闭ROS2发布器...")
                self.ros2_publisher.shutdown()

            # 原有清理代码继续...
"""

# ============================================
# 使用说明
# ============================================

USAGE = """
使用步骤：

1. 在 simulate_full_flow.py 的第38行之后添加导入
2. 在 __init__ 方法末尾（第240行左右）添加初始化代码
3. 在 run() 方法开始处添加启动代码
4. 在主循环IK求解后（第650行左右）添加滤波和发布代码
5. 在 finally 块中添加清理代码

或者使用自动化脚本：
    python3 scripts/apply_high_freq_patch.py
"""

if __name__ == '__main__':
    print("=" * 80)
    print("simulate_full_flow.py 高频插值补丁")
    print("=" * 80)
    print()
    print(USAGE)
    print()
    print("详细修改内容请查看此文件中的各个部分")