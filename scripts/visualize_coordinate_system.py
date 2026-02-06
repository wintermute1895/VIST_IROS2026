#!/usr/bin/env python3
"""
可视化视觉模块输出的坐标系方向

显示：
1. 肩膀坐标系的 X, Y, Z 轴方向
2. 实时关键点坐标值
3. 坐标轴方向指示（通过颜色和箭头）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from src.nodes.vision_node_depth import VisionNodeWithDepth


class CoordinateSystemVisualizer(VisionNodeWithDepth):
    """扩展 VisionNodeWithDepth，添加坐标系可视化"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print("\n" + "=" * 60)
        print("坐标系可视化工具")
        print("=" * 60)
        print("\n📐 肩膀坐标系定义（输出坐标系）：")
        print("   X 轴（红色）：向上（垂直方向）")
        print("   Y 轴（绿色）：向右（水平方向）")
        print("   Z 轴（蓝色）：向前（水平方向，手臂延伸）")
        print("\n原点：肩部位置（动态归零）")
        print("\n操作：")
        print("   - 抬起手臂：X 增大（向上）")
        print("   - 向右移动：Y 增大（向右）")
        print("   - 向前伸手：Z 增大（向前）")
        print("\n按 'q' 或 ESC 退出")
        print("=" * 60)
        print()

    def draw_coordinate_axes(self, frame, origin_pixel, scale=100):
        """
        在图像上绘制坐标轴
        :param frame: 图像
        :param origin_pixel: 原点像素坐标 (x, y)
        :param scale: 坐标轴长度（像素）
        """
        ox, oy = origin_pixel

        # X 轴（红色）：向上
        # 在图像坐标系中，Y 减小表示向上
        cv2.arrowedLine(frame, (ox, oy), (ox, oy - scale), (0, 0, 255), 3, tipLength=0.3)
        cv2.putText(frame, "X (Up)", (ox + 5, oy - scale - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Y 轴（绿色）：向右
        # 在图像坐标系中，X 增大表示向右
        cv2.arrowedLine(frame, (ox, oy), (ox + scale, oy), (0, 255, 0), 3, tipLength=0.3)
        cv2.putText(frame, "Y (Right)", (ox + scale + 10, oy - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Z 轴（蓝色）：向前
        # 向前在 2D 图像中无法直接表示，用对角线表示深度
        # 向右下表示"向前"（远离相机）
        cv2.arrowedLine(frame, (ox, oy), (ox + int(scale*0.7), oy + int(scale*0.7)),
                       (255, 0, 0), 3, tipLength=0.3)
        cv2.putText(frame, "Z (Forward)", (ox + int(scale*0.7) + 10, oy + int(scale*0.7) + 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    def draw_keypoint_info(self, frame, keypoints):
        """
        在图像上显示关键点坐标信息
        :param frame: 图像
        :param keypoints: 关键点字典
        """
        if keypoints is None:
            return

        # 在右侧显示坐标信息
        x_start = frame.shape[1] - 300
        y_start = 30
        line_height = 25

        # 背景框
        cv2.rectangle(frame, (x_start - 10, y_start - 20),
                     (frame.shape[1] - 10, y_start + line_height * 6),
                     (0, 0, 0), -1)
        cv2.rectangle(frame, (x_start - 10, y_start - 20),
                     (frame.shape[1] - 10, y_start + line_height * 6),
                     (255, 255, 255), 2)

        # 标题
        cv2.putText(frame, "Keypoint Coordinates (m)", (x_start, y_start),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        y = y_start + line_height

        # 显示每个关键点的坐标
        for name, coords in keypoints.items():
            x, y_coord, z = coords
            # 颜色编码：X=红，Y=绿，Z=蓝
            text = f"{name:10s}: X={x:+.3f} Y={y_coord:+.3f} Z={z:+.3f}"
            cv2.putText(frame, text, (x_start, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            y += line_height

    def draw_direction_indicators(self, frame, keypoints):
        """
        绘制方向指示器（显示手臂运动方向）
        :param frame: 图像
        :param keypoints: 关键点字典
        """
        if keypoints is None:
            return

        # 获取手腕位置
        wrist = np.array(keypoints['wrist'])

        # 在左下角显示方向指示
        x_start = 20
        y_start = frame.shape[0] - 150
        box_size = 120

        # 背景框
        cv2.rectangle(frame, (x_start, y_start),
                     (x_start + box_size, y_start + box_size),
                     (0, 0, 0), -1)
        cv2.rectangle(frame, (x_start, y_start),
                     (x_start + box_size, y_start + box_size),
                     (255, 255, 255), 2)

        # 标题
        cv2.putText(frame, "Direction", (x_start + 10, y_start + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # 显示主要方向
        y = y_start + 45
        directions = []

        # X 方向（上/下）
        if wrist[0] > 0.1:
            directions.append(("UP", (0, 0, 255)))
        elif wrist[0] < -0.1:
            directions.append(("DOWN", (0, 0, 255)))

        # Y 方向（右/左）
        if wrist[1] > 0.1:
            directions.append(("RIGHT", (0, 255, 0)))
        elif wrist[1] < -0.1:
            directions.append(("LEFT", (0, 255, 0)))

        # Z 方向（前/后）
        if wrist[2] > 0.1:
            directions.append(("FORWARD", (255, 0, 0)))
        elif wrist[2] < -0.1:
            directions.append(("BACKWARD", (255, 0, 0)))

        # 显示方向
        for direction, color in directions:
            cv2.putText(frame, direction, (x_start + 10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            y += 25

        if not directions:
            cv2.putText(frame, "CENTER", (x_start + 10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 2)

    def process_frame(self):
        """重写 process_frame，添加坐标系可视化"""
        frame, keypoints = super().process_frame()

        if frame is None:
            return None, None

        # 如果检测到姿态，添加可视化
        if keypoints is not None:
            # 获取肩部像素坐标（作为坐标系原点）
            # 由于肩部在机器人坐标系中是 [0, 0, 0]，我们需要从图像中找到它
            h, w = frame.shape[:2]

            # 假设肩部在图像中心偏上的位置
            # 这里我们需要从 MediaPipe 的像素坐标获取
            # 但为了简化，我们在图像左上角绘制坐标轴
            origin_pixel = (150, 150)

            # 绘制坐标轴
            self.draw_coordinate_axes(frame, origin_pixel, scale=80)

            # 显示关键点坐标信息
            self.draw_keypoint_info(frame, keypoints)

            # 显示方向指示器
            self.draw_direction_indicators(frame, keypoints)

            # 添加说明文字
            cv2.putText(frame, "Shoulder Frame (Origin at Shoulder)",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        return frame, keypoints


if __name__ == "__main__":
    try:
        # 创建可视化节点
        visualizer = CoordinateSystemVisualizer(
            udp_ip="127.0.0.1",
            udp_port=6001,
            scale=1.0,
            width=640,
            height=480,
            fps=30
        )

        # 运行
        visualizer.run(show_window=True)

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
