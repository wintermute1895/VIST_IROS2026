"""
多线程 VIST 控制脚本
使用 4 线程架构实现高频率控制

性能提升：
- 控制频率：37Hz → 100Hz (2.7x)
- UDP 通信：JSON → MessagePack (5-10x)
- TCP 健康监控：自动重连

创建日期：2026-02-18
"""

import sys
import time
import signal
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import VISTConfig, get_config
from src.control.vist_controller import VISTController
from src.control.threaded_vist_controller import ThreadedVISTController
from src.robot.robot_interface import RobotInterface
from src.communication.udp_receiver import UDPReceiver
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    logger.info("\n收到停止信号，正在安全关闭...")
    global running
    running = False


def main():
    """主函数"""
    global running
    running = True

    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("=" * 60)
    logger.info("多线程 VIST 控制系统")
    logger.info("=" * 60)

    # 1. 加载配置
    logger.info("\n[1/5] 加载配置...")
    config = VISTConfig()
    logger.info(f"  机器人模式: {config.robot_mode}")
    logger.info(f"  意图检测: {'启用' if config.enable_intent_detection else '禁用'}")

    # 2. 初始化 UDP 接收器
    logger.info("\n[2/5] 初始化 UDP 接收器...")
    udp_receiver = UDPReceiver(
        host=config.udp_host,
        port=config.udp_port
    )
    udp_receiver.connect()

    # 3. 初始化机器人接口
    logger.info("\n[3/5] 初始化机器人接口...")
    robot_interface = RobotInterface(config)
    robot_interface.connect()

    # 检查 TCP 连接健康状态
    if hasattr(robot_interface.driver, 'is_connection_healthy'):
        logger.info(f"  TCP 健康监控: 已启用")

    # 4. 初始化 VIST 控制器
    logger.info("\n[4/5] 初始化 VIST 控制器...")
    vist_controller = VISTController(config)

    # 5. 初始化多线程控制器
    logger.info("\n[5/5] 初始化多线程控制器...")
    threaded_controller = ThreadedVISTController(
        vist_controller=vist_controller,
        robot_interface=robot_interface,
        udp_receiver=udp_receiver,
        visualizer=None  # 可选：添加可视化器
    )

    logger.info("\n" + "=" * 60)
    logger.info("系统初始化完成")
    logger.info("=" * 60)
    logger.info("\n线程架构:")
    logger.info("  - Vision Thread:        30 Hz (UDP 接收)")
    logger.info("  - Control Thread:      100 Hz (VIST 处理 + 命令发送)")
    logger.info("  - Visualization Thread: 10 Hz (可视化)")
    logger.info("  - Stats Thread:          1 Hz (性能监控)")
    logger.info("\n优化方案:")
    logger.info("  - MessagePack 序列化 (5-10x 性能提升)")
    logger.info("  - 包丢失检测 (seq + timestamp)")
    logger.info("  - TCP 健康监控 (自动重连)")
    logger.info("\n按 Ctrl+C 停止")
    logger.info("=" * 60 + "\n")

    # 启动多线程控制器
    threaded_controller.start()

    try:
        # 主循环：监控系统状态
        last_stats_time = time.time()
        stats_interval = 10.0  # 每10秒打印一次详细统计

        while running and threaded_controller.is_running():
            time.sleep(0.1)

            # 定期打印详细统计
            current_time = time.time()
            if current_time - last_stats_time >= stats_interval:
                logger.info("\n" + "=" * 60)
                logger.info("系统状态报告")
                logger.info("=" * 60)

                # 多线程控制器统计
                stats = threaded_controller.get_statistics()
                logger.info("\n业务统计:")
                logger.info(f"  Vision 接收: {stats.get('vision_packets_received', 0)} 包")
                logger.info(f"  Control 发送: {stats.get('control_commands_sent', 0)} 命令")
                logger.info(f"  Control 失败: {stats.get('control_failures', 0)} 次")
                logger.info(f"  Viz 渲染: {stats.get('viz_frames_rendered', 0)} 帧")

                # 线程频率统计
                if 'thread_frequencies' in stats:
                    logger.info("\n线程频率:")
                    for name, freq in stats['thread_frequencies'].items():
                        logger.info(f"  {name}: {freq:.1f} Hz")

                # UDP 统计
                udp_stats = udp_receiver.get_statistics()
                logger.info("\nUDP 通信:")
                logger.info(f"  接收包数: {udp_stats['packets_received']}")
                logger.info(f"  丢包数: {udp_stats['packets_lost']}")
                logger.info(f"  丢包率: {udp_stats['loss_rate']:.2f}%")
                logger.info(f"  平均延迟: {udp_stats['avg_latency_ms']:.2f} ms")
                logger.info(f"  最大延迟: {udp_stats['max_latency_ms']:.2f} ms")

                # TCP 连接健康状态
                if hasattr(robot_interface.driver, 'get_connection_statistics'):
                    tcp_stats = robot_interface.driver.get_connection_statistics()
                    logger.info("\nTCP 连接:")
                    logger.info(f"  健康状态: {'✅ 正常' if tcp_stats['healthy'] else '❌ 异常'}")
                    logger.info(f"  失败次数: {tcp_stats['failures']}")
                    logger.info(f"  最后读取: {tcp_stats['time_since_last_read']:.2f} 秒前")

                logger.info("=" * 60 + "\n")

                last_stats_time = current_time

    except KeyboardInterrupt:
        logger.info("\n收到键盘中断")
    except Exception as e:
        logger.error(f"\n运行时错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # 安全关闭
        logger.info("\n正在安全关闭系统...")

        logger.info("  停止多线程控制器...")
        threaded_controller.stop()

        logger.info("  关闭机器人连接...")
        robot_interface.disconnect()

        logger.info("  关闭 UDP 接收器...")
        udp_receiver.close()

        logger.info("\n✅ 系统已安全关闭")


if __name__ == "__main__":
    main()
