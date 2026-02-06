#!/usr/bin/env python3
"""
坐标系方向测试 - 在视频画面上实时显示坐标值

显示内容：
1. 左上角：坐标轴（红=X, 绿=Y, 蓝=Z）
2. 右侧：实时坐标值（大字体，易读）
3. 左下角：方向指示器
4. 中央：当前测试提示
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from src.nodes.vision_node_depth import VisionNodeWithDepth


class CoordinateTestVisualizer(VisionNodeWithDepth):
    """坐标系测试可视化器 - 在画面上显示所有信息"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_step = 0
        self.test_instructions = [
            "1. 抬起手臂 → 观察 X 值增大",
            "2. 放下手臂 → 观察 X 值减小",
            "3. 向右移动 → 观察 Y 值增大",
            "4. 向左移动 → 观察 Y 值减小",
            "5. 向前伸手 → 观察 Z 值增大",
            "6. 向后收手 → 观察 Z 值减小"
        ]
        print("\n" + "=" * 70)
        print("坐标系方向测试 - 视频画面显示")
        print("=" * 70)
        print("\n坐标系定义：")
        print("  X 轴（红色）：向上")
        print("  Y 轴（绿色）：向右")
        print("  Z 轴（蓝色）：向前（实际是向后）")
        print("\n按空格键切换测试步骤")
        print("按 'q' 或 ESC 退出")
        print("=" * 70)
        print()

    def draw_coordinate_axes(self, frame):
        """绘制坐标轴（左上角）"""
        ox, oy = 100, 100
        scale = 60

        # 背景框
        cv2.rectangle(frame, (20, 20), (200, 180), (0, 0, 0), -1)
        cv2.rectangle(frame, (20, 20), (200, 180), (255, 255, 255), 2)

        # 标题
        cv2.putText(frame, "Axes", (30, 45),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # X 轴（红色）：向上
        cv2.arrowedLine(frame, (ox, oy), (ox, oy - scale), (0, 0, 255), 2, tipLength=0.3)
        cv2.putText(frame, "X", (ox + 5, oy - scale - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Y 轴（绿色）：向右
        cv2.arrowedLine(frame, (ox, oy), (ox + scale, oy), (0, 255, 0), 2, tipLength=0.3)
        cv2.putText(frame, "Y", (ox + scale + 5, oy - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Z 轴（蓝色）：向前（对角线表示）
        cv2.arrowedLine(frame, (ox, oy), (ox + int(scale*0.7), oy + int(scale*0.7)),
                       (255, 0, 0), 2, tipLength=0.3)
        cv2.putText(frame, "Z", (ox + int(scale*0.7) + 5, oy + int(scale*0.7) + 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    def draw_large_coordinates(self, frame, keypoints):
        """在右侧显示大字体坐标值"""
        if keypoints is None:
            return

        # 右侧显示区域
        x_start = frame.shape[1] - 280
        y_start = 50
        line_height = 60

        # 背景框
        cv2.rectangle(frame, (x_start - 20, y_start - 30),
                     (frame.shape[1] - 20, y_start + line_height * 3 + 20),
                     (0, 0, 0), -1)
        cv2.rectangle(frame, (x_start - 20, y_start - 30),
                     (frame.shape[1] - 20, y_start + line_height * 3 + 20),
                     (255, 255, 255), 3)

        # 标题
        cv2.putText(frame, "Wrist Position", (x_start, y_start - 5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 获取手腕坐标
        wrist = keypoints['wrist']
        x, y, z = wrist

        # 显示坐标（大字体）
        y_pos = y_start + line_height
        cv2.putText(frame, f"X: {x:+.3f}m", (x_start, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        y_pos += line_height
        cv2.putText(frame, f"Y: {y:+.3f}m", (x_start, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        y_pos += line_height
        cv2.putText(frame, f"Z: {z:+.3f}m", (x_start, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 0, 0), 2)

    def draw_direction_indicator(self, frame, keypoints):
        """在左下角显示方向指示"""
        if keypoints is None:
            return

        wrist = np.array(keypoints['wrist'])

        # 左下角显示区域
        x_start = 20
        y_start = frame.shape[0] - 180
        box_width = 200
        box_height = 160

        # 背景框
        cv2.rectangle(frame, (x_start, y_start),
                     (x_start + box_width, y_start + box_height),
                     (0, 0, 0), -1)
        cv2.rectangle(frame, (x_start, y_start),
                     (x_start + box_width, y_start + box_height),
                     (255, 255, 255), 3)

        # 标题
        cv2.putText(frame, "Direction", (x_start + 10, y_start + 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # 显示方向
        y = y_start + 65
        directions = []

        # X 方向
        if wrist[0] > 0.05:
            directions.append(("UP", (0, 0, 255)))
        elif wrist[0] < -0.05:
            directions.append(("DOWN", (0, 0, 255)))

        # Y 方向
        if wrist[1] > 0.05:
            directions.append(("RIGHT", (0, 255, 0)))
        elif wrist[1] < -0.05:
            directions.append(("LEFT", (0, 255, 0)))

        # Z 方向
        if wrist[2] > 0.05:
            directions.append(("FORWARD", (255, 0, 0)))
        elif wrist[2] < -0.05:
            directions.append(("BACK", (255, 0, 0)))

        # 显示方向
        if directions:
            for direction, color in directions:
                cv2.putText(frame, direction, (x_start + 15, y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                y += 35
        else:
            cv2.putText(frame, "CENTER", (x_start + 15, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)

    def draw_test_instruction(self, frame):
        """在中央上方显示当前测试指令"""
        instruction = self.test_instructions[self.test_step % len(self.test_instructions)]

        # 中央上方显示区域
        text_size = cv2.getTextSize(instruction, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
        x_center = (frame.shape[1] - text_size[0]) // 2
        y_pos = 30

        # 背景框
        padding = 15
        cv2.rectangle(frame,
                     (x_center - padding, y_pos - text_size[1] - padding),
                     (x_center + text_size[0] + padding, y_pos + padding),
                     (0, 0, 0), -1)
        cv2.rectangle(frame,
                     (x_center - padding, y_pos - text_size[1] - padding),
                     (x_center + text_size[0] + padding, y_pos + padding),
                     (255, 255, 0), 2)

        # 显示指令
        cv2.putText(frame, instruction, (x_center, y_pos),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        # 显示提示
        hint = "Press SPACE for next test"
        hint_size = cv2.getTextSize(hint, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        hint_x = (frame.shape[1] - hint_size[0]) // 2
        cv2.putText(frame, hint, (hint_x, y_pos + 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    def process_frame(self):
        """重写 process_frame，添加所有可视化"""
        frame, keypoints = super().process_frame()

        if frame is None:
            return None, None

        # 绘制所有可视化元素
        self.draw_coordinate_axes(frame)
        self.draw_test_instruction(frame)

        if keypoints is not None:
            self.draw_large_coordinates(frame, keypoints)
            self.draw_direction_indicator(frame, keypoints)

        return frame, keypoints

    def run(self, show_window=True):
        """运行测试循环"""
        print("🚀 开始测试...")

        try:
            while True:
                frame, keypoints = self.process_frame()

                if frame is None:
                    continue

                # 发送关键点数据
                if keypoints is not None:
                    self.send_keypoints(keypoints)

                # 显示窗口
                if show_window:
                    cv2.imshow("Coordinate System Test", frame)

                    # 按键处理
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q') or key == 27:  # 'q' 或 ESC
                        break
                    elif key == ord(' '):  # 空格键
                        self.test_step += 1
                        print(f"测试步骤 {self.test_step % len(self.test_instructions) + 1}: "
                              f"{self.test_instructions[self.test_step % len(self.test_instructions)]}")

        except KeyboardInterrupt:
            print("\n⏹️ 收到停止信号")

        finally:
            self.pipeline.stop()
            self.pose.close()
            self.sock.close()
            if show_window:
                cv2.destroyAllWindows()
            print("✅ 测试完成")


if __name__ == "__main__":
    try:
        visualizer = CoordinateTestVisualizer(
            udp_ip="127.0.0.1",
            udp_port=6001,
            scale=1.0,
            width=640,
            height=480,
            fps=30
        )
        visualizer.run(show_window=True)

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
