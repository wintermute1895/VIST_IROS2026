#!/usr/bin/env python3
"""
控制频率不匹配仿真测试

模拟真实系统中的频率不匹配问题：
- 视觉采样: 30Hz (不规则)
- 控制循环: 50Hz (固定)
- 机器人响应: 20Hz (有延迟)

目的：验证VIST卡尔曼滤波器能否处理频率不匹配
"""

import os
import sys
import time
import threading
import queue
import numpy as np
import pinocchio as pin
from collections import deque

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from src.config import get_config
from src.core.vist_kalman_filter import VISTKalmanFilter
from src.core.ik_solver import PinocchioIKSolver
from src.core.geometric_arm_solver import GeometricArmSolver


class VisionSimulator(threading.Thread):
    """
    视觉模拟器（30Hz，不规则采样）

    模拟真实相机的特性：
    - 目标频率30Hz，但实际会有抖动（28-32Hz）
    - 偶尔丢帧（5%概率）
    - 数据有噪声
    """

    def __init__(self, data_queue, target_freq=30, jitter=0.1, drop_rate=0.05):
        """
        Args:
            data_queue: 数据队列（发送给控制器）
            target_freq: 目标频率（Hz）
            jitter: 频率抖动比例（0-1）
            drop_rate: 丢帧率（0-1）
        """
        super().__init__(daemon=True)
        self.data_queue = data_queue
        self.target_freq = target_freq
        self.target_dt = 1.0 / target_freq
        self.jitter = jitter
        self.drop_rate = drop_rate
        self.running = False

        # 统计信息
        self.frame_count = 0
        self.dropped_frames = 0

    def run(self):
        """视觉线程主循环"""
        self.running = True
        print(f"📷 [Vision] 启动 (目标频率: {self.target_freq}Hz)")

        start_time = time.time()

        while self.running:
            loop_start = time.time()

            # 模拟丢帧
            if np.random.random() < self.drop_rate:
                self.dropped_frames += 1
                time.sleep(self.target_dt)
                continue

            # 生成测试数据（圆周运动）
            t = time.time() - start_time
            radius = 0.3
            center = np.array([0.3, 0.0, 0.8])

            # 目标位置（圆周运动）
            target_pos = center + np.array([
                radius * np.cos(2 * np.pi * t / 5.0),
                radius * np.sin(2 * np.pi * t / 5.0),
                0.0
            ])

            # 添加噪声（模拟视觉检测误差）
            noise = np.random.normal(0, 0.002, 3)  # 2mm标准差
            target_pos += noise

            # 发送数据（带时间戳）
            data = {
                'timestamp': time.time(),
                'target_pos': target_pos,
                'frame_id': self.frame_count
            }

            try:
                self.data_queue.put_nowait(data)
            except queue.Full:
                print("⚠️ [Vision] 数据队列满，丢弃帧")

            self.frame_count += 1

            # 模拟频率抖动
            jitter_factor = 1.0 + np.random.uniform(-self.jitter, self.jitter)
            sleep_time = self.target_dt * jitter_factor

            elapsed = time.time() - loop_start
            if elapsed < sleep_time:
                time.sleep(sleep_time - elapsed)

        print(f"📷 [Vision] 停止 (总帧数: {self.frame_count}, 丢帧: {self.dropped_frames})")

    def stop(self):
        """停止视觉线程"""
        self.running = False


class RobotSimulator(threading.Thread):
    """
    机器人模拟器（20Hz响应，有延迟）

    模拟真实机器人的特性：
    - 指令处理频率20Hz（比控制频率低）
    - 运动有延迟（惯性）
    - 指令队列有限（最多5个）
    """

    def __init__(self, command_queue, model, data, controlled_indices, max_queue_size=5):
        """
        Args:
            command_queue: 指令队列（接收控制器指令）
            model: Pinocchio模型
            data: Pinocchio数据
            controlled_indices: 受控关节索引
            max_queue_size: 最大指令队列长度
        """
        super().__init__(daemon=True)
        self.command_queue = command_queue
        self.model = model
        self.data = data
        self.controlled_indices = controlled_indices
        self.max_queue_size = max_queue_size
        self.running = False

        # 机器人状态
        self.q_current = pin.neutral(model).copy()
        self.q_target = self.q_current.copy()

        # 运动参数（模拟惯性）
        self.max_velocity = 0.5  # rad/s
        self.response_time = 0.1  # 响应时间常数（秒）

        # 统计信息
        self.command_count = 0
        self.dropped_commands = 0

    def run(self):
        """机器人线程主循环"""
        self.running = True
        freq = 20  # Hz
        dt = 1.0 / freq

        print(f"🤖 [Robot] 启动 (响应频率: {freq}Hz)")

        while self.running:
            loop_start = time.time()

            # 1. 接收新指令（非阻塞）
            try:
                while not self.command_queue.empty():
                    if self.command_queue.qsize() > self.max_queue_size:
                        # 队列溢出，丢弃旧指令
                        self.command_queue.get_nowait()
                        self.dropped_commands += 1
                    else:
                        cmd = self.command_queue.get_nowait()
                        self.q_target = cmd['q_cmd']
                        self.command_count += 1
            except queue.Empty:
                pass

            # 2. 模拟运动（一阶惯性系统）
            # q_current = q_current + (q_target - q_current) * (1 - exp(-dt/tau))
            alpha = 1.0 - np.exp(-dt / self.response_time)
            delta = self.q_target - self.q_current

            # 速度限制
            max_delta = self.max_velocity * dt
            delta = np.clip(delta, -max_delta, max_delta)

            self.q_current += alpha * delta

            # 3. 控制频率
            elapsed = time.time() - loop_start
            if elapsed < dt:
                time.sleep(dt - elapsed)

        print(f"🤖 [Robot] 停止 (接收指令: {self.command_count}, 丢弃: {self.dropped_commands})")

    def get_state(self):
        """获取当前状态"""
        return self.q_current.copy()

    def stop(self):
        """停止机器人线程"""
        self.running = False


class ControllerSimulator:
    """
    控制器模拟器（50Hz固定频率）

    核心测试对象：验证VIST能否处理频率不匹配
    """

    def __init__(self, config, ik_solver, vist_filter, vision_queue, robot_queue):
        """
        Args:
            config: 配置对象
            ik_solver: IK求解器
            vist_filter: VIST卡尔曼滤波器
            vision_queue: 视觉数据队列（输入）
            robot_queue: 机器人指令队列（输出）
        """
        self.config = config
        self.ik_solver = ik_solver
        self.vist_filter = vist_filter
        self.vision_queue = vision_queue
        self.robot_queue = robot_queue

        # 控制参数
        self.control_freq = 50  # Hz
        self.control_dt = 1.0 / self.control_freq

        # 数据缓存
        self.last_vision_data = None
        self.last_vision_time = None

        # 统计信息
        self.control_count = 0
        self.vision_update_count = 0
        self.prediction_only_count = 0

        # 性能记录
        self.vision_delays = deque(maxlen=100)  # 视觉数据延迟
        self.control_errors = deque(maxlen=100)  # 控制误差

    def run(self, duration=10.0):
        """
        运行控制循环

        Args:
            duration: 运行时长（秒）
        """
        print(f"🎮 [Controller] 启动 (控制频率: {self.control_freq}Hz)")
        print(f"   视觉频率: 30Hz → 控制频率: 50Hz → 机器人频率: 20Hz")
        print(f"   测试VIST能否处理频率不匹配...\n")

        start_time = time.time()
        last_print_time = start_time

        try:
            while time.time() - start_time < duration:
                loop_start = time.time()

                # ==========================================
                # 1. 检查是否有新的视觉数据
                # ==========================================
                has_new_vision = False
                try:
                    vision_data = self.vision_queue.get_nowait()
                    self.last_vision_data = vision_data
                    self.last_vision_time = vision_data['timestamp']
                    has_new_vision = True
                    self.vision_update_count += 1

                    # 记录视觉延迟
                    vision_delay = time.time() - vision_data['timestamp']
                    self.vision_delays.append(vision_delay * 1000)  # ms

                except queue.Empty:
                    # 没有新数据，使用预测
                    self.prediction_only_count += 1

                # ==========================================
                # 2. VIST求解（关键测试点）
                # ==========================================
                if has_new_vision and self.last_vision_data is not None:
                    # 有新观测：预测 + 更新
                    target_pos = self.last_vision_data['target_pos']
                    q_solution, success, error = self.vist_filter.solve(
                        target_pos=target_pos,
                        target_quat=np.array([0, 0, 0, 1])
                    )
                else:
                    # 没有新观测：只预测
                    self.vist_filter.predict()
                    q_solution = self.vist_filter.state[:self.vist_filter.n_joints]
                    success = True
                    error = 0.0

                # ==========================================
                # 3. 发送指令到机器人
                # ==========================================
                if success:
                    # 扩展到完整模型
                    q_full = pin.neutral(self.ik_solver.model).copy()
                    for i, ctrl_idx in enumerate(self.ik_solver.controlled_indices):
                        if i < len(q_solution) and ctrl_idx < len(q_full):
                            q_full[ctrl_idx] = q_solution[i]

                    cmd = {
                        'q_cmd': q_full,
                        'timestamp': time.time()
                    }

                    try:
                        self.robot_queue.put_nowait(cmd)
                    except queue.Full:
                        print("⚠️ [Controller] 机器人指令队列满")

                self.control_count += 1

                # ==========================================
                # 4. 状态显示（每秒一次）
                # ==========================================
                if time.time() - last_print_time >= 1.0:
                    self._print_status()
                    last_print_time = time.time()

                # ==========================================
                # 5. 控制频率
                # ==========================================
                elapsed = time.time() - loop_start
                if elapsed < self.control_dt:
                    time.sleep(self.control_dt - elapsed)
                else:
                    print(f"⚠️ [Controller] 控制循环超时: {elapsed*1000:.1f}ms > {self.control_dt*1000:.1f}ms")

        except KeyboardInterrupt:
            print("\n⏹️ 用户中断")

        finally:
            self._print_final_statistics()

    def _print_status(self):
        """打印实时状态"""
        vision_rate = self.vision_update_count / self.control_count * 100 if self.control_count > 0 else 0
        prediction_rate = self.prediction_only_count / self.control_count * 100 if self.control_count > 0 else 0

        avg_delay = np.mean(self.vision_delays) if self.vision_delays else 0

        status = f"✅ 控制帧: {self.control_count} | "
        status += f"视觉更新: {vision_rate:.1f}% | "
        status += f"纯预测: {prediction_rate:.1f}% | "
        status += f"视觉延迟: {avg_delay:.1f}ms"

        if hasattr(self.vist_filter, 'alpha_smoothed'):
            status += f" | 意图: {self.vist_filter.alpha_smoothed:.2f}"

        print(status)

    def _print_final_statistics(self):
        """打印最终统计"""
        print("\n" + "=" * 80)
        print("📊 最终统计")
        print("=" * 80)

        print(f"\n🎮 控制器:")
        print(f"   总控制帧数: {self.control_count}")
        print(f"   视觉更新次数: {self.vision_update_count}")
        print(f"   纯预测次数: {self.prediction_only_count}")

        if self.control_count > 0:
            vision_rate = self.vision_update_count / self.control_count * 100
            prediction_rate = self.prediction_only_count / self.control_count * 100
            print(f"   视觉更新率: {vision_rate:.1f}%")
            print(f"   纯预测率: {prediction_rate:.1f}%")

        if self.vision_delays:
            print(f"\n📷 视觉延迟:")
            print(f"   平均: {np.mean(self.vision_delays):.1f}ms")
            print(f"   最大: {np.max(self.vision_delays):.1f}ms")
            print(f"   最小: {np.min(self.vision_delays):.1f}ms")

        print("\n" + "=" * 80)


def main():
    """主函数"""
    print("=" * 80)
    print("🧪 控制频率不匹配仿真测试")
    print("=" * 80)

    # 1. 加载配置
    print("\n📁 加载配置...")
    config = get_config()

    # 2. 初始化IK求解器
    print("\n🧠 初始化IK求解器...")
    urdf_path = os.path.join(project_root, "config", "lkls73_o2_dual_arm_description.urdf")
    ik_solver = PinocchioIKSolver(
        urdf_path=urdf_path,
        end_effector_frame="Right_Wrist_Roll_Link"
    )

    # 3. 初始化几何求解器（如果启用）
    geometric_solver = None
    if config.vist_geometric_solver_enabled:
        print("\n🧮 初始化几何求解器...")
        geometric_solver = GeometricArmSolver(
            model=ik_solver.model,
            data=ik_solver.data,
            controlled_joints=ik_solver.controlled_indices,
            ee_frame_id=ik_solver.ee_frame_id,
            config=config
        )

    # 4. 初始化VIST滤波器
    print("\n🔬 初始化VIST滤波器...")
    vist_filter = VISTKalmanFilter(
        ik_solver,
        config,
        geometric_solver=geometric_solver
    )

    # 5. 创建数据队列
    vision_queue = queue.Queue(maxsize=10)  # 视觉数据队列
    robot_queue = queue.Queue(maxsize=10)   # 机器人指令队列

    # 6. 启动视觉模拟器（30Hz）
    vision_sim = VisionSimulator(
        data_queue=vision_queue,
        target_freq=30,
        jitter=0.1,      # 10%频率抖动
        drop_rate=0.05   # 5%丢帧率
    )
    vision_sim.start()

    # 7. 启动机器人模拟器（20Hz）
    robot_sim = RobotSimulator(
        command_queue=robot_queue,
        model=ik_solver.model,
        data=ik_solver.data,
        controlled_indices=ik_solver.controlled_indices,
        max_queue_size=5
    )
    robot_sim.start()

    # 8. 等待线程启动
    time.sleep(0.5)

    # 9. 运行控制器（50Hz）
    controller = ControllerSimulator(
        config=config,
        ik_solver=ik_solver,
        vist_filter=vist_filter,
        vision_queue=vision_queue,
        robot_queue=robot_queue
    )

    print("\n✅ 初始化完成！")
    print("\n提示：按 Ctrl+C 停止测试\n")

    # 运行10秒
    controller.run(duration=10.0)

    # 10. 停止所有线程
    print("\n🛑 停止所有线程...")
    vision_sim.stop()
    robot_sim.stop()

    # 等待线程结束
    vision_sim.join(timeout=1.0)
    robot_sim.join(timeout=1.0)

    print("\n✅ 测试完成！")


if __name__ == "__main__":
    main()
