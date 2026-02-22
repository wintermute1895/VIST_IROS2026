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
from src.control.trajectory_interpolator import TrajectoryInterpolator
from src.control.filters import LowPassFilter
from src.robot.robot_interface import RobotInterface
from src.robot.visualizer import RobotVisualizer
from src.utils.performance_monitor import TeleopMetrics
from src.utils.logger import setup_logger

# 设置日志
logger = setup_logger(__name__)


class RealRobotVIST:
    """VIST 真机控制主程序（协调器）"""

    def __init__(self, enable_visualization=None):
        """
        初始化真机控制器

        Args:
            enable_visualization: 是否启用可视化（None=从配置读取）
        """
        logger.info("="*80)
        logger.info("VIST 真机控制系统（重构版）")
        logger.info("="*80)

        # 1. 加载配置
        logger.info("加载系统配置...")
        self.config = get_config()
        logger.info("配置加载完成")

        # 2. 初始化 VIST 控制器（算法层）
        self.controller = VISTController(self.config)

        # 3. 初始化机器人接口（硬件层）
        self.robot = RobotInterface(self.config)

        # 3.5 初始化轨迹插值器（平滑层）
        self.interpolator = TrajectoryInterpolator(
            max_velocity=self.config.max_joint_velocity,
            max_acceleration=self.config.max_joint_acceleration,
            dt=self.config.control_dt
        )
        logger.info("轨迹插值器初始化完成")

        # 3.6 初始化低通滤波器（VIST输出平滑）
        # 用于抑制VIST输出的跳变，在SafeRobotController之前工作
        filter_alpha = getattr(self.config, 'vist_output_filter_alpha', 0.2)
        self.vist_output_filter = LowPassFilter(alpha=filter_alpha, n_dims=7)
        logger.info(f"VIST输出滤波器初始化完成 (alpha={filter_alpha})")

        # 4. 初始化性能监控器
        self.perf_metrics = TeleopMetrics()
        logger.info("性能监控器初始化完成")

        # 5. 初始化可视化器（可选）
        if enable_visualization is None:
            enable_visualization = self.config.visualization_enable

        self.visualizer = None
        if enable_visualization:
            logger.info("初始化可视化器...")
            try:
                self.visualizer = RobotVisualizer(
                    model=self.controller.ik_solver.model,
                    collision_model=self.controller.ik_solver.collision_model,
                    visual_model=self.controller.ik_solver.visual_model,
                    enable=True
                )
                if self.visualizer.enable:
                    logger.info(f"可视化器初始化成功: {self.visualizer.get_url()}")
            except Exception as e:
                logger.warning(f"可视化器初始化失败: {e}")
                self.visualizer = None

        logger.info("初始化完成！")

    def connect(self):
        """连接到真机"""
        q_init = self.robot.connect()

        # 保存初始关节位置（用于关节锁定）
        self.q_init = q_init.copy()

        # 重置轨迹插值器状态
        self.interpolator.reset(q_init)
        logger.info("轨迹插值器状态已重置")

        # 重置VIST输出滤波器状态
        self.vist_output_filter.reset(q_init)
        logger.info("VIST输出滤波器状态已重置")

        # 读取关节使能配置
        if hasattr(self.config, 'robot_joint_enabled'):
            self.joint_enabled = self.config.robot_joint_enabled
            logger.info("关节使能配置:")
            for i, enabled in enumerate(self.joint_enabled):
                status = "✅ 使能" if enabled else "🔒 锁定"
                logger.info(f"  Joint {i}: {status}")
        else:
            # 默认所有关节使能
            self.joint_enabled = [True] * len(q_init)
            logger.info("未配置关节使能，默认所有关节使能")

        # 初始化控制器的当前状态
        import pinocchio as pin
        import numpy as np
        q_full = pin.neutral(self.controller.ik_solver.model).copy()
        for i, ctrl_idx in enumerate(self.controller.ik_solver.controlled_indices):
            if i < len(q_init) and ctrl_idx < len(q_full):
                q_full[ctrl_idx] = q_init[i]
        self.controller.q_current = q_full

        # 初始化安全控制器的当前状态
        # ✅ 关键修复：同时初始化current和previous，避免第一帧速度计算错误
        self.controller.safety_controller.q_current = q_init.copy()
        self.controller.safety_controller.q_previous = q_init.copy()
        self.controller.safety_controller.q_dot_current = np.zeros(7)
        self.controller.safety_controller.q_dot_previous = np.zeros(7)
        self.controller.safety_controller.last_update_time = time.time()

    def run(self, duration=None, countdown_seconds=10, hold_position_after=False):
        """
        运行真机控制循环

        Args:
            duration: 运行时长（秒），None=从配置读取
            countdown_seconds: 启动前倒计时（秒）
            hold_position_after: 结束后是否保持位置（True=保持使能，False=断开连接）
        """
        if duration is None:
            duration = self.config.control_duration

        print("\n" + "=" * 80)
        print("🚀 准备启动遥操作控制")
        print("=" * 80)

        print("\n⚠️  安全提示：")
        print("   1. 确保机器人周围无障碍物")
        print("   2. 确保紧急停止按钮可用")
        print("   3. 确保视觉节点正在运行")
        print("   4. 按 Ctrl+C 可随时停止")

        # 倒计时（给操作员时间走到摄像头前）
        print("\n" + "=" * 80)
        print("📹 请操作员就位")
        print("=" * 80)
        print(f"⏱️  {countdown_seconds} 秒后开始遥操作")
        print("\n请利用这段时间：")
        print("  1. 从电脑前走到摄像头视野内")
        print("  2. 调整站位，确保身体在摄像头中心")
        print("  3. 确认手臂在摄像头视野内")
        print("  4. 准备开始操作")
        print("\n倒计时：")

        for i in range(countdown_seconds, 0, -1):
            print(f"   {i}...", end='\r', flush=True)
            time.sleep(1)
        print("   🚀 倒计时结束！" + " " * 20)

        # 等待第一个UDP包（确保第一帧对齐）
        print("\n⏳ 等待第一个UDP数据包...")
        print("   ⚠️  这确保了第一帧对齐，避免突然的大幅运动")
        print("   ⚠️  请在另一个终端启动数据回放器")
        print("   💡 提示：可以慢慢启动，没有时间限制\n")

        first_packet = None
        wait_count = 0
        while first_packet is None:
            # 直接从UDP接收器读取，避免触发robot_interface的超时警告
            first_packet = self.robot.udp_receiver.receive()
            if first_packet is None:
                time.sleep(0.1)  # 100ms休眠，避免CPU占用过高
                wait_count += 1
                # 每10秒打印一次提示（100次 * 0.1s = 10s）
                if wait_count % 100 == 0:
                    print(f"   ⏳ 仍在等待... (已等待 {wait_count // 10} 秒)")

        print("   ✅ 收到第一个数据包，开始控制！\n")

        # 重置robot_interface的超时计数器
        self.robot.data_timeout_count = 0

        # ✅ 关键修复：重置SafeRobotController的时间戳
        # 避免倒计时和等待UDP包期间的时间累积导致第一帧dt_actual异常
        self.controller.safety_controller.last_update_time = time.time()

        # 收到第一个包后才开始计时
        start_time = time.time()
        frame_count = 0
        success_count = 0
        last_print_time = time.time()
        last_robot_update = time.time()  # 上次更新机器人的时间

        # 缓存最新的UDP数据（使用第一个包初始化）
        if 'keypoints' in first_packet:
            cached_keypoints = first_packet['keypoints']
        else:
            cached_keypoints = first_packet
        cached_timestamp = first_packet.get('timestamp', time.time())
        last_udp_time = time.time()

        try:
            while time.time() - start_time < duration:
                loop_start = time.time()

                # ==========================================
                # Phase 1: 非阻塞接收UDP数据（更新缓存）
                # ==========================================
                # ✅ 修复：直接使用UDP接收器，避免在每次循环迭代都触发超时逻辑
                # 原来的 receive_keypoints() 会在每次调用时增加超时计数器
                # 这导致在高频循环中快速触发超时警告
                self.perf_metrics.monitor.start_timer("receive_keypoints")
                packet = self.robot.udp_receiver.receive()
                self.perf_metrics.monitor.stop_timer("receive_keypoints")

                if packet is not None:
                    # 提取关键点数据（兼容新旧格式）
                    if 'keypoints' in packet:
                        human_keypoints = packet['keypoints']
                    else:
                        human_keypoints = packet

                    # 检查关键点是否完整
                    if 'wrist' in human_keypoints and 'elbow' in human_keypoints:
                        # 更新缓存
                        cached_keypoints = human_keypoints
                        cached_timestamp = time.time()
                        last_udp_time = time.time()
                        # ✅ 重置超时计数器（只在成功接收数据时）
                        self.robot.data_timeout_count = 0

                # ==========================================
                # Phase 2: 检查是否需要更新机器人
                # ==========================================
                time_since_last_update = time.time() - last_robot_update
                should_update_robot = time_since_last_update >= self.config.control_dt

                # 如果还没到更新时间，精确休眠
                if not should_update_robot:
                    time_until_next_update = self.config.control_dt - time_since_last_update
                    if time_until_next_update > 0.001:
                        # 休眠到距离目标时间还剩0.5ms
                        sleep_time = max(0, time_until_next_update - 0.0005)
                        if sleep_time > 0:
                            time.sleep(sleep_time)
                    continue

                # 如果没有缓存数据，跳过本次更新
                if cached_keypoints is None:
                    time.sleep(0.001)
                    continue

                # ✅ 检查UDP数据超时（只在实际更新机器人时检查）
                # 这样超时检查在控制频率下进行，而不是循环频率
                time_since_last_udp = time.time() - last_udp_time
                udp_timeout_threshold = self.config.control_dt * self.robot.max_data_timeout
                if time_since_last_udp > udp_timeout_threshold:
                    if frame_count % 30 == 0:  # 每30帧打印一次，避免刷屏
                        print(f"\n⚠️ UDP数据超时: {time_since_last_udp:.2f}s (阈值: {udp_timeout_threshold:.2f}s)")
                    # 发送当前位置（停止运动）
                    try:
                        _, q_current, _ = self.robot.driver.get_state()
                        self.robot.driver.send_command(q_current)
                    except Exception as e:
                        logger.warning(f"发送停止命令失败: {e}")
                    time.sleep(0.001)
                    continue

                # ==========================================
                # Phase 3: 更新机器人（使用缓存的数据）
                # ==========================================
                self.perf_metrics.monitor.start_timer("total_loop")

                # 2. VIST 控制器处理
                self.perf_metrics.monitor.start_timer("vist_process")
                q_target, success, debug_info = self.controller.process(cached_keypoints)
                self.perf_metrics.monitor.stop_timer("vist_process")

                if not success:
                    # 处理失败，跳过此帧
                    self.perf_metrics.record_failure()
                    if frame_count % 30 == 0:
                        logger.warning(f"控制失败: {debug_info.get('error', 'Unknown')}")
                    self.perf_metrics.monitor.stop_timer("total_loop")
                    last_robot_update = time.time()  # 即使失败也更新时间，保持频率稳定
                    continue

                self.perf_metrics.record_success()
                success_count += 1

                # 2.4 应用低通滤波器（平滑VIST输出）
                # ✅ 在关节锁定和安全控制器之前添加滤波
                # 这样可以抑制VIST输出的跳变，减少SafeRobotController的触发频率
                q_filtered = self.vist_output_filter.update(q_target)

                # ✅ 测量实际控制周期（关键修复！）
                # 使用实际测量的dt而不是固定配置值
                current_time = time.time()
                dt_actual = current_time - last_robot_update
                # 防止异常值（第一帧或长时间暂停）
                if dt_actual > 1.0 or dt_actual < 0.001:
                    dt_actual = self.config.control_dt

                # 2.5 应用关节锁定（⚠️ 必须在安全控制器之前！）
                # 原因：SafeRobotController会计算速度 q_dot = (q_target - q_current) / dt
                # 如果锁定的关节在q_target中有变化，会触发错误的速度限制
                # 解决方案：先锁定关节，让SafeRobotController看到的q_target中锁定关节没有变化
                import numpy as np
                q_locked = q_filtered.copy()  # ✅ 使用滤波后的输出
                for i in range(len(q_locked)):
                    if i < len(self.joint_enabled) and not self.joint_enabled[i]:
                        # 锁定的关节保持初始位置
                        q_locked[i] = self.q_init[i]

                # 2.6 轨迹插值（平滑处理）
                # ⚠️ 临时禁用插值器进行测试
                # 在 VIST 求解和关节锁定之间插入插值器
                # 这样可以避免"咣当"现象（突然的速度/加速度变化）
                # ✅ 传递实际dt给插值器
                # q_interpolated = self.interpolator.interpolate(q_locked, dt_actual=dt_actual)
                # 临时直接使用q_locked，跳过插值器
                q_interpolated = q_locked

                # 2.7 安全控制器（像仿真一样在主循环中调用）
                # ✅ 关键修复：不在VISTController内部调用，而是在主循环中调用
                # 这样可以避免速度估计问题，保证平滑性
                # ✅ 现在SafeRobotController接收的是锁定后的q_interpolated
                # 锁定的关节不会触发速度限制
                safety_status = {}
                if hasattr(self.controller, 'safety_controller'):
                    q_safe, safety_status = self.controller.safety_controller.process_command(q_interpolated)
                    debug_info['safety_status'] = safety_status
                else:
                    q_safe = q_interpolated

                # 3. 最终命令（已经锁定，直接使用）
                q_command = q_safe

                # 4. 发送到真机（blocking参数由配置文件控制：当前为false=非阻塞）
                self.perf_metrics.monitor.start_timer("send_command")
                self.robot.send_command(q_command, blocking=self.config.hardware_move_joint_block)
                self.perf_metrics.monitor.stop_timer("send_command")

                # 4.5 读取实际关节状态（闭环反馈）
                # 这是关键：用实际位置而不是命令位置来更新控制器状态
                q_tracking_error = None
                try:
                    _, q_actual, _ = self.robot.driver.get_state()

                    # 计算关节跟踪误差（命令 vs 实际）
                    q_tracking_error = np.linalg.norm(q_command - q_actual)

                    # 同步插值器状态（使用实际位置）
                    # 这确保插值器基于真实位置进行下一步规划
                    # 注意：先同步插值器，以便获取插值器的速度估计
                    self.interpolator.q_current = q_actual.copy()

                    # 获取插值器的当前速度（基于梯形速度曲线）
                    q_dot_interpolator = self.interpolator.get_current_velocity()

                    # ✅ 关键修复：直接传递速度给安全控制器，避免重复计算
                    # 这样可以确保速度状态一致，避免加速度计算错误
                    self.controller.safety_controller.update_actual_command(
                        q_actual, q_dot_actual=q_dot_interpolator
                    )

                except Exception as e:
                    # 如果读取失败，使用命令值作为备选（开环模式）
                    if frame_count % 100 == 0:
                        logger.warning(f"读取实际状态失败: {e}，使用命令值")
                    self.controller.safety_controller.update_actual_command(q_command)

                # 5. 记录跟踪误差（如果有）
                if 'target_pos' in debug_info and 'current_pos' in debug_info:
                    error = np.linalg.norm(
                        np.array(debug_info['target_pos']) -
                        np.array(debug_info['current_pos'])
                    )
                    self.perf_metrics.record_tracking_error(error)

                    # 记录位置和时间戳（用于计算平滑度）
                    self.perf_metrics.record_position(
                        np.array(debug_info['target_pos']),
                        time.time()
                    )

                # 记录关节角度（用于关节运动统计）
                # 注意：记录实际发送的指令，而不是安全控制器输出的指令
                self.perf_metrics.record_joint_angles(q_command)

                # 6. 更新可视化
                if self.visualizer is not None and self.visualizer.enable:
                    self.visualizer.update(self.controller.q_current)

                frame_count += 1
                last_robot_update = time.time()  # 更新机器人更新时间

                # 停止总循环计时
                self.perf_metrics.monitor.stop_timer("total_loop")

                # 6. 状态显示（每秒一次）
                if time.time() - last_print_time >= 1.0:
                    success_rate = (success_count / frame_count * 100) if frame_count > 0 else 0

                    status_msg = f"✅ 帧数: {frame_count} | 成功率: {success_rate:.1f}%"

                    # 添加性能指标
                    loop_stats = self.perf_metrics.monitor.get_stats("total_loop")
                    if loop_stats:
                        status_msg += f" | 延迟: {loop_stats['mean']*1000:.1f}ms"
                        status_msg += f" | 频率: {loop_stats['frequency']:.1f}Hz"
                        status_msg += f" | dt_actual: {dt_actual*1000:.1f}ms"

                    # VIST 意图因子
                    if hasattr(self.controller.vist_filter, 'alpha_smoothed'):
                        status_msg += f" | 意图: {self.controller.vist_filter.alpha_smoothed:.2f}"

                    # 关节跟踪误差（闭环反馈）
                    if q_tracking_error is not None:
                        status_msg += f" | 跟踪误差: {q_tracking_error:.4f}rad"

                    # 关节锁定状态
                    locked_joints = [i for i in range(len(self.joint_enabled)) if not self.joint_enabled[i]]
                    if locked_joints:
                        status_msg += f" | 🔒锁定: {locked_joints}"

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

        except KeyboardInterrupt:
            logger.info("用户中断")
        except Exception as e:
            logger.error(f"运行时错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 根据参数决定是保持位置还是断开连接
            if hold_position_after:
                self.robot.hold_position()
                print("\n⚠️  机器人保持当前位置，仍处于使能状态")
                print("   按 Ctrl+C 可退出程序并断开连接")
                try:
                    # 保持程序运行，直到用户手动中断
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n用户中断，正在断开连接...")
                    self.robot.disconnect()
            else:
                # 断开连接
                self.robot.disconnect()

            # 打印性能摘要
            print("\n" + "="*80)
            print("📊 性能报告")
            print("="*80)

            # 基础统计
            print(f"\n基础统计:")
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
            if 'safety_controller' in safety_stats:
                sc_stats = safety_stats['safety_controller']
                print(f"\n🛡️  安全控制统计:")
                print(f"  速度限制: {sc_stats['velocity_limited_count']}次")
                print(f"  加速度限制: {sc_stats['acceleration_limited_count']}次")
                print(f"  位置限制: {sc_stats['position_limited_count']}次")

            # 关闭可视化器
            if self.visualizer is not None:
                self.visualizer.close()

            logger.info("真机控制器已退出")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="VIST 真机控制系统（重构版）")
    parser.add_argument("--duration", type=float, default=60.0,
                        help="运行时长（秒），默认60秒")
    parser.add_argument("--countdown", type=int, default=10,
                        help="启动前倒计时（秒）")
    parser.add_argument("--hold", action="store_true",
                        help="结束后保持位置（不下使能）")
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
        countdown_seconds=args.countdown,
        hold_position_after=args.hold
    )


if __name__ == "__main__":
    main()
