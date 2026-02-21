#!/usr/bin/env python3
"""
============================================================================
LinkerHand L10 基于视觉的控制系统 - 主入口
============================================================================
功能：基于视觉的遥操作，带状态机控制
架构：摄像头 → 视觉控制器 → LinkerHand驱动 → 硬件

控制流程：
1. 从摄像头捕获图像帧
2. 使用视觉控制器处理（MediaPipe + 状态机）
3. 根据手部状态获取目标关节角度
4. 通过LinkerHandDriver发送命令到硬件
5. 显示可视化

按 'q' 键安全退出
============================================================================
"""

import sys
import os
import time
import logging
import argparse
import cv2
import numpy as np
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

# ============================================================================
# 将项目根目录添加到Python路径
# ============================================================================
# 此脚本位于scripts/目录，需要访问src/模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # 向上一级到VIST/

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 现在可以导入我们的模块
from src.robot.hand_driver import LinkerHandDriver
from src.core.vision_controller import VisionController
from src.core.camera_wrapper import CameraFactory
from src.core.config import Config, CameraType, GraspPreset


# ============================================================================
# 中文文本绘制辅助函数
# ============================================================================

def draw_chinese_text(img: np.ndarray,
                     text: str,
                     position: Tuple[int, int],
                     color: Tuple[int, int, int],
                     size: int = 20) -> np.ndarray:
    """
    使用 PIL 在 OpenCV 图像上绘制中文文本

    参数：
        img: OpenCV 图像 (BGR 格式)
        text: 要绘制的文本（支持中文）
        position: 文本位置 (x, y)
        color: 文本颜色 (B, G, R) - OpenCV 格式
        size: 字体大小

    返回：
        绘制了文本的图像
    """
    # 将 OpenCV 图像 (BGR) 转换为 PIL 图像 (RGB)
    img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)

    # 尝试加载中文字体
    font = None
    chinese_font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "C:\\Windows\\Fonts\\msyh.ttc",  # Windows
    ]

    for font_path in chinese_font_paths:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, size)
                break
            except Exception:
                continue

    # 如果找不到中文字体，使用默认字体并打印警告
    if font is None:
        try:
            font = ImageFont.load_default()
            # 只在第一次警告
            if not hasattr(draw_chinese_text, '_warned'):
                logging.warning("未找到中文字体，使用默认字体。中文可能无法正确显示。")
                draw_chinese_text._warned = True
        except Exception:
            font = None

    # 将 OpenCV 的 BGR 颜色转换为 RGB
    color_rgb = (color[2], color[1], color[0])

    # 绘制文本
    draw.text(position, text, font=font, fill=color_rgb)

    # 转换回 OpenCV 图像 (BGR)
    img_bgr = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    return img_bgr


class HandControlSystem:
    """
    完整的基于视觉的手部控制系统

    集成：
    - 摄像头捕获（OpenCV）
    - 视觉处理（VisionController）
    - 硬件控制（LinkerHandDriver）
    """

    def __init__(self,
                 camera_type: CameraType = CameraType.OPENCV,
                 camera_id: int = 0,
                 mock_mode: bool = False,
                 can_id: int = 0x27,
                 can_channel: str = "can0",
                 control_freq: int = 30,
                 grasp_preset: GraspPreset = GraspPreset.MEDIUM):
        """
        初始化控制系统

        参数：
            camera_type: 摄像头类型（OpenCV或RealSense）
            camera_id: 摄像头设备ID（仅用于OpenCV）
            mock_mode: 如果为True，在无硬件模式下运行
            can_id: LinkerHand的CAN设备ID
            can_channel: CAN接口名称
            control_freq: 控制循环频率（Hz）
            grasp_preset: 抓取预设类型（小/中/大物体）
        """
        self.logger = logging.getLogger(__name__)
        self.control_freq = control_freq
        self.target_loop_time = 1.0 / control_freq
        self.camera_type = camera_type
        self.grasp_preset = grasp_preset

        self.logger.info("=" * 70)
        self.logger.info("正在初始化手部控制系统")
        self.logger.info("=" * 70)

        # 初始化摄像头
        self._init_camera(camera_type, camera_id)

        # 初始化视觉控制器
        self.logger.info("正在初始化视觉控制器...")
        self.vision_controller = VisionController(
            min_detection_confidence=Config.vision.MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=Config.vision.MIN_TRACKING_CONFIDENCE,
            grasp_preset=grasp_preset
        )

        # 初始化硬件驱动
        self.logger.info("正在初始化LinkerHand驱动...")
        self.hand_driver = LinkerHandDriver(
            can_id=can_id,
            can_channel=can_channel,
            mock_mode=mock_mode,
            enable_filtering=True  # 启用基于变化的过滤
        )

        self.logger.info("=" * 70)
        self.logger.info("✅ 系统初始化成功")
        self.logger.info(f"  摄像头类型: {camera_type.value}")
        self.logger.info(f"  模拟模式: {mock_mode}")
        self.logger.info(f"  控制频率: {control_freq} Hz")
        self.logger.info(f"  抓取预设: {grasp_preset.value}")
        self.logger.info("=" * 70)

    def _init_camera(self, camera_type: CameraType, camera_id: int):
        """初始化摄像头"""
        self.logger.info(f"正在初始化摄像头 (类型: {camera_type.value})...")

        # 使用摄像头工厂创建摄像头实例
        self.camera = CameraFactory.create_camera(camera_type, camera_id)

        # 打开摄像头
        if not self.camera.open():
            raise RuntimeError(f"无法打开摄像头 (类型: {camera_type.value})")

        self.logger.info("✅ 摄像头初始化完成")

        # 创建窗口并设置为可调整大小
        cv2.namedWindow(Config.control.WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(Config.control.WINDOW_NAME,
                        Config.control.WINDOW_WIDTH,
                        Config.control.WINDOW_HEIGHT)

    def _draw_enhanced_info_panel(self,
                                  frame: np.ndarray,
                                  target_angles: List[float],
                                  pinch_ratio: Optional[float],
                                  frame_count: int,
                                  commands_sent: int,
                                  start_time: float) -> np.ndarray:
        """
        绘制增强的信息面板

        参数：
            frame: 输入图像
            target_angles: 目标关节角度列表
            pinch_ratio: 捏合比率
            frame_count: 帧计数
            commands_sent: 已发送命令数
            start_time: 开始时间

        返回：
            带有信息面板的图像
        """
        h, w = frame.shape[:2]

        # ============================================================
        # 右侧信息面板
        # ============================================================
        panel_width = 280
        panel_x = w - panel_width - 10
        panel_y = 10

        # 绘制半透明背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (panel_x, panel_y),
                     (w - 10, h - 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # 绘制边框
        cv2.rectangle(frame, (panel_x, panel_y),
                     (w - 10, h - 50), (100, 100, 100), 2)

        # ============================================================
        # 标题
        # ============================================================
        y = panel_y + 30
        # 使用中文绘制函数
        frame = draw_chinese_text(frame, "关节角度 (度)", (panel_x + 10, y - 18),
                                  (255, 255, 255), size=24)

        y += 10
        cv2.line(frame, (panel_x + 10, y), (w - 20, y), (100, 100, 100), 1)

        # ============================================================
        # 关节角度显示（所有10个关节）
        # ============================================================
        joint_names = [
            "拇指俯仰", "拇指偏航", "食指俯仰", "中指俯仰",
            "无名指俯仰", "小指俯仰", "食指侧摆", "无名指侧摆",
            "小指侧摆", "拇指侧摆"
        ]

        y += 25
        for i in range(10):
            # 关节名称 - 使用中文绘制
            name_text = f"{joint_names[i]}:"
            frame = draw_chinese_text(frame, name_text, (panel_x + 15, y - 12),
                                     (200, 200, 200), size=16)

            # 角度值（右对齐）
            angle_text = f"{target_angles[i]:6.1f}"
            cv2.putText(frame, angle_text, (panel_x + 180, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 255, 100), 1)

            # 角度条（可视化）
            bar_x = panel_x + 15
            bar_y = y + 5
            bar_width = 240
            bar_height = 4

            # 背景条
            cv2.rectangle(frame, (bar_x, bar_y),
                         (bar_x + bar_width, bar_y + bar_height),
                         (50, 50, 50), -1)

            # 角度条（0-255度映射到条宽度）
            angle_normalized = min(max(target_angles[i], 0), 255) / 255.0
            filled_width = int(bar_width * angle_normalized)

            # 根据角度值选择颜色
            if target_angles[i] < 85:
                bar_color = (0, 100, 255)  # 橙色（低角度）
            elif target_angles[i] < 170:
                bar_color = (0, 255, 255)  # 黄色（中角度）
            else:
                bar_color = (0, 255, 0)    # 绿色（高角度）

            cv2.rectangle(frame, (bar_x, bar_y),
                         (bar_x + filled_width, bar_y + bar_height),
                         bar_color, -1)

            y += 35


        # ============================================================
        # 底部统计信息栏
        # ============================================================

        # 底部区域高度
        bottom_bar_height = 70
        bottom_bar_y = h - bottom_bar_height

        # 绘制底部栏背景（更高的半透明背景）
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, bottom_bar_y), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # ============================================================
        # 左下角：统计信息
        # ============================================================
        left_x = 15
        info_y_start = bottom_bar_y + 25

        # 帧数
        frame_text = f"帧数: {frame_count}"
        frame = draw_chinese_text(frame, frame_text, (left_x, h-30),
                                 (100, 200, 255), size=22)


        # ============================================================
        # 底部居中：操作提示（独立一行）
        # ============================================================
        hint_y = h - 15
        hint_text = "按 'q'退出 | 'r'重置 "

        # 计算文本宽度以居中显示（估算）
        hint_x = w // 2 - 120  # 大致居中

        frame = draw_chinese_text(frame, hint_text, (hint_x, hint_y - 15),
                                 (180, 180, 180), size=18)

        return frame

    def run(self):
        """
        主控制循环

        处理流程：
        1. 捕获图像帧包含
        2. 使用视觉控制器处理
        3. 发送命令到硬件
        4. 显示可视化
        5. 处理键盘输入
        """
        self.logger.info("\n" + "=" * 70)
        self.logger.info("启动控制循环")
        self.logger.info("按键说明:")
        self.logger.info("  'q' - 退出")
        self.logger.info("  'r' - 重置机械手到零位")
        self.logger.info("  's' - 打印系统状态")
        self.logger.info("  '1' - 切换到小物体抓取预设")
        self.logger.info("  '2' - 切换到中等物体抓取预设")
        self.logger.info("  '3' - 切换到大物体抓取预设")
        self.logger.info("=" * 70 + "\n")

        frame_count = 0
        commands_sent = 0
        start_time = time.time()

        try:
            while True:
                loop_start = time.time()

                # ============================================================
                # 步骤1：捕获图像帧
                # ============================================================
                ret, frame, depth_frame = self.camera.read()
                if not ret or frame is None:
                    self.logger.error("无法从摄像头读取图像帧")
                    break

                # 镜像翻转（对用户更直观）
                frame = cv2.flip(frame, 1)

                # ============================================================
                # 步骤2：使用视觉控制器处理
                # ============================================================
                target_angles, hand_detected, pinch_ratio = \
                    self.vision_controller.process_frame(frame)

                # ============================================================
                # 步骤3：发送命令到硬件
                # ============================================================
                success = self.hand_driver.move(target_angles)

                if success:
                    commands_sent += 1

                # ============================================================
                # 步骤4：显示可视化
                # ============================================================
                # 绘制手部关键点和状态
                frame = self.vision_controller.draw_visualization(
                    frame, hand_detected, pinch_ratio
                )

                # 绘制增强的信息面板
                frame = self._draw_enhanced_info_panel(
                    frame, target_angles, pinch_ratio,
                    frame_count, commands_sent, start_time
                )

                # 显示图像帧
                cv2.imshow(Config.control.WINDOW_NAME, frame)

                # ============================================================
                # 步骤5：处理键盘输入
                # ============================================================
                key = cv2.waitKey(1) & 0xFF

                if key == ord('q'):
                    self.logger.info("用户请求退出")
                    break
                elif key == ord('r'):
                    self.logger.info("🔄 用户请求重置到IDLE状态（完全张开）")

                    # 1. 重置视觉控制器状态（启动冷却机制）
                    self.vision_controller.reset_state()

                    # 2. 立即发送硬件指令到IDLE位置（全255度）
                    idle_position = [255.0] * 10
                    success = self.hand_driver.move(idle_position)

                    if success:
                        self.logger.info("✅ 硬件已设置到IDLE位置")
                    else:
                        self.logger.warning("⚠️  硬件设置失败")
                elif key == ord('1'):
                    # 切换到小物体抓取预设
                    self.logger.info("🔄 切换到小物体抓取预设")
                    self.vision_controller.switch_grasp_preset(GraspPreset.SMALL)
                    self.grasp_preset = GraspPreset.SMALL
                elif key == ord('2'):
                    # 切换到中等物体抓取预设
                    self.logger.info("🔄 切换到中等物体抓取预设")
                    self.vision_controller.switch_grasp_preset(GraspPreset.MEDIUM)
                    self.grasp_preset = GraspPreset.MEDIUM
                elif key == ord('3'):
                    # 切换到大物体抓取预设
                    self.logger.info("🔄 切换到大物体抓取预设")
                    self.vision_controller.switch_grasp_preset(GraspPreset.LARGE)
                    self.grasp_preset = GraspPreset.LARGE
                elif key == ord('s'):
                    # 打印状态
                    self.logger.info("\n" + "=" * 70)
                    self.logger.info("系统状态:")
                    self.logger.info("=" * 70)
                    self.logger.info(f"视觉控制器: {self.vision_controller.get_status()}")
                    self.logger.info(f"手部驱动: {self.hand_driver.get_status()}")
                    self.logger.info("=" * 70 + "\n")

                # ============================================================
                # 控制循环时序
                # ============================================================
                loop_time = time.time() - loop_start
                if loop_time < self.target_loop_time:
                    time.sleep(self.target_loop_time - loop_time)

        except KeyboardInterrupt:
            self.logger.info("\n⚠️  用户中断 (Ctrl+C)")

        except Exception as e:
            self.logger.error(f"\n❌ 主循环错误: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self._cleanup()

    def _cleanup(self):
        """安全清理和关闭"""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("正在关闭系统...")
        self.logger.info("=" * 70)

        # 退出前设置为IDLE位置（全255度 - 完全张开）
        self.logger.info("正在设置机械手到IDLE位置（全255度）...")
        try:
            idle_position = [255.0] * 10
            self.hand_driver.move(idle_position)
            time.sleep(0.5)
            self.logger.info("✅ 机械手已设置到IDLE位置")
        except Exception as e:
            self.logger.warning(f"设置IDLE位置时警告: {e}")

        # 关闭视觉控制器
        self.logger.info("正在关闭视觉控制器...")
        try:
            self.vision_controller.close()
        except Exception as e:
            self.logger.warning(f"关闭视觉控制器时警告: {e}")

        # 释放摄像头
        self.logger.info("正在释放摄像头...")
        if hasattr(self, 'camera'):
            self.camera.release()

        # 关闭所有OpenCV窗口
        cv2.destroyAllWindows()

        self.logger.info("=" * 70)
        self.logger.info("✅ 关闭完成")
        self.logger.info("=" * 70)


# ============================================================================
# 主入口点
# ============================================================================

def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        description='LinkerHand L10 基于视觉的控制系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
说明：
  所有参数都有默认值（在 src/core/config.py 中配置）
  可以直接运行: python run_hand.py
  也可以使用命令行参数覆盖配置文件中的值

示例：
  # 使用配置文件中的默认设置运行
  python run_hand.py

  # 在模拟模式下运行（无硬件）
  python run_hand.py --mock

  # 使用不同的摄像头
  python run_hand.py --camera 1

  # 使用Intel RealSense D435i摄像头
  python run_hand.py --camera-type realsense

  # 更改控制频率
  python run_hand.py --freq 20

  # 使用大物体抓取预设
  python run_hand.py --grasp-preset large

  # 调试模式（详细日志）
  python run_hand.py --log-level DEBUG

配置文件：
  修改 src/core/config.py 可以更改默认设置
        """
    )

    parser.add_argument(
        '--camera-type',
        type=str,
        default=None,  # None表示使用配置文件中的值
        choices=['opencv', 'realsense'],
        help=f'摄像头类型 (默认: {Config.camera.CAMERA_TYPE.value})'
    )

    parser.add_argument(
        '--camera',
        type=int,
        default=None,  # None表示使用配置文件中的值
        help=f'摄像头设备ID (仅用于OpenCV类型，默认: {Config.camera.OPENCV_CAMERA_ID})'
    )

    parser.add_argument(
        '--mock',
        action='store_true',
        default=None,  # None表示使用配置文件中的值
        help=f'在模拟模式下运行（无硬件） (默认: {Config.hardware.MOCK_MODE})'
    )

    parser.add_argument(
        '--can-id',
        type=lambda x: int(x, 0),  # 支持十六进制输入如0x27
        default=None,  # None表示使用配置文件中的值
        help=f'CAN设备ID (默认: 0x{Config.hardware.CAN_ID:02X})'
    )

    parser.add_argument(
        '--can-channel',
        type=str,
        default=None,  # None表示使用配置文件中的值
        help=f'CAN接口名称 (默认: {Config.hardware.CAN_CHANNEL})'
    )

    parser.add_argument(
        '--freq',
        type=int,
        default=None,  # None表示使用配置文件中的值
        help=f'控制循环频率（Hz） (默认: {Config.control.CONTROL_FREQ})'
    )

    parser.add_argument(
        '--grasp-preset',
        type=str,
        default=None,  # None表示使用配置文件中的值
        choices=['small', 'medium', 'large'],
        help=f'抓取预设类型 (默认: {Config.joint_angles.DEFAULT_GRASP_PRESET.value})'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default=None,  # None表示使用配置文件中的值
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help=f'日志级别 (默认: {Config.log.LOG_LEVEL})'
    )

    args = parser.parse_args()

    # 从配置文件读取默认值，命令行参数可以覆盖
    camera_type = CameraType.OPENCV if args.camera_type == 'opencv' else (
        CameraType.REALSENSE if args.camera_type == 'realsense' else Config.camera.CAMERA_TYPE
    )

    camera_id = args.camera if args.camera is not None else Config.camera.OPENCV_CAMERA_ID

    mock_mode = args.mock if args.mock is not None else Config.hardware.MOCK_MODE

    can_id = args.can_id if args.can_id is not None else Config.hardware.CAN_ID

    can_channel = args.can_channel if args.can_channel is not None else Config.hardware.CAN_CHANNEL

    control_freq = args.freq if args.freq is not None else Config.control.CONTROL_FREQ

    grasp_preset_map = {
        'small': GraspPreset.SMALL,
        'medium': GraspPreset.MEDIUM,
        'large': GraspPreset.LARGE
    }
    grasp_preset = grasp_preset_map.get(args.grasp_preset, Config.joint_angles.DEFAULT_GRASP_PRESET)

    log_level = args.log_level if args.log_level is not None else Config.log.LOG_LEVEL

    # 设置日志
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=Config.log.LOG_FORMAT,
        datefmt=Config.log.LOG_DATE_FORMAT
    )

    # 打印横幅
    print("\n" + "=" * 70)
    print("  LinkerHand L10 基于视觉的控制系统")
    print("  使用MediaPipe手部追踪的状态机控制")
    print("=" * 70)
    print(f"摄像头类型:     {camera_type.value}")
    if camera_type == CameraType.OPENCV:
        print(f"摄像头ID:       {camera_id}")
    print(f"模拟模式:       {mock_mode}")
    print(f"CAN ID:          0x{can_id:02X}")
    print(f"CAN通道:     {can_channel}")
    print(f"控制频率:    {control_freq} Hz")
    print(f"抓取预设:       {grasp_preset.value}")
    print(f"日志级别:       {log_level}")
    print("=" * 70)
    print("\n控制键:")
    print("  'q' - 退出")
    print("  'r' - 重置机械手到零位")
    print("  's' - 打印系统状态")
    print("  '1' - 切换到小物体抓取预设")
    print("  '2' - 切换到中等物体抓取预设")
    print("  '3' - 切换到大物体抓取预设")
    print("=" * 70 + "\n")

    try:
        # 初始化并运行系统
        system = HandControlSystem(
            camera_type=camera_type,
            camera_id=camera_id,
            mock_mode=mock_mode,
            can_id=can_id,
            can_channel=can_channel,
            control_freq=control_freq,
            grasp_preset=grasp_preset
        )

        system.run()

    except Exception as e:
        logging.error(f"\n❌ 系统失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
