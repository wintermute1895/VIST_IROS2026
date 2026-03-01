"""
实时角度显示窗口
使用 Tkinter 创建一个独立窗口显示肘部角度信息
"""

import tkinter as tk
from tkinter import ttk
import threading
from typing import Optional


class AngleDisplayWindow:
    """实时角度显示窗口"""

    def __init__(self):
        """初始化窗口"""
        self.root = None
        self.labels = {}
        self.running = False
        self.thread = None

    def start(self):
        """启动窗口（在单独的线程中）"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_window, daemon=True)
        self.thread.start()

    def _run_window(self):
        """运行窗口主循环"""
        self.root = tk.Tk()
        self.root.title("肘部角度实时监控")
        self.root.geometry("600x420")  # 增大窗口尺寸以容纳新标签
        self.root.configure(bg='#2b2b2b')

        # 设置窗口始终在最前面
        self.root.attributes('-topmost', True)

        # 设置窗口关闭事件处理器
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        # 标题
        title_label = tk.Label(
            self.root,
            text="肘部角度调试信息",
            font=("Arial", 24, "bold"),  # 增大标题字体
            bg='#2b2b2b',
            fg='#ffffff'
        )
        title_label.pack(pady=15)

        # 创建显示框架
        frame = tk.Frame(self.root, bg='#2b2b2b')
        frame.pack(pady=15, padx=30, fill=tk.BOTH, expand=True)

        # 向量夹角
        self._create_label_pair(frame, "向量夹角:", "vector_angle", "#4CAF50", 0)

        # 人体肘部角度
        self._create_label_pair(frame, "人体肘部角度:", "elbow_angle_human", "#2196F3", 1)

        # 电机角度（计算值）
        self._create_label_pair(frame, "电机角度 (计算):", "elbow_angle_motor", "#FF9800", 2)

        # 电机实际角度（滤波后）
        self._create_label_pair(frame, "电机实际角度:", "actual_motor_angle", "#FF5722", 3)

        # 原始 q4
        self._create_label_pair(frame, "原始 q4:", "q4_raw", "#999999", 4)

        # 运行主循环
        try:
            self.root.mainloop()
        except:
            pass
        finally:
            self.running = False

    def _create_label_pair(self, parent, text, key, color, row):
        """创建标签对（名称 + 值）"""
        # 名称标签
        name_label = tk.Label(
            parent,
            text=text,
            font=("Arial", 18),  # 增大字体
            bg='#2b2b2b',
            fg='#cccccc',
            anchor='w'
        )
        name_label.grid(row=row, column=0, sticky='w', pady=8)

        # 值标签
        value_label = tk.Label(
            parent,
            text="--",
            font=("Arial", 22, "bold"),  # 增大字体
            bg='#2b2b2b',
            fg=color,
            anchor='e'
        )
        value_label.grid(row=row, column=1, sticky='e', pady=8)

        # 配置列权重
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        # 保存标签引用
        self.labels[key] = value_label

    def update(self, debug_info: dict):
        """
        更新显示的角度信息

        Args:
            debug_info: 调试信息字典，包含：
                - 'vector_angle': 向量夹角（度）
                - 'elbow_angle_human': 人体肘部角度（度）
                - 'elbow_angle_motor': 电机角度（度，计算值）
                - 'actual_motor_angle': 电机实际角度（度，滤波后）
                - 'q4_raw': 原始 q4（弧度）
        """
        if not self.running or self.root is None:
            return

        try:
            # 使用 after 方法在主线程中更新 UI
            self.root.after(0, self._update_labels, debug_info)
        except:
            pass

    def _on_closing(self):
        """窗口关闭事件处理器"""
        self.running = False
        try:
            if self.root is not None:
                self.root.quit()
                self.root.destroy()
        except:
            pass

    def _update_labels(self, debug_info: dict):
        """在主线程中更新标签"""
        try:
            if 'vector_angle' in debug_info:
                self.labels['vector_angle'].config(
                    text=f"{debug_info['vector_angle']:.1f}°"
                )

            if 'elbow_angle_human' in debug_info:
                self.labels['elbow_angle_human'].config(
                    text=f"{debug_info['elbow_angle_human']:.1f}°"
                )

            if 'elbow_angle_motor' in debug_info:
                self.labels['elbow_angle_motor'].config(
                    text=f"{debug_info['elbow_angle_motor']:.1f}°"
                )

            if 'actual_motor_angle' in debug_info:
                self.labels['actual_motor_angle'].config(
                    text=f"{debug_info['actual_motor_angle']:.1f}°"
                )

            if 'q4_raw' in debug_info:
                self.labels['q4_raw'].config(
                    text=f"{debug_info['q4_raw']:.3f} rad"
                )
        except:
            pass

    def stop(self):
        """停止窗口"""
        self.running = False
        if self.root is not None:
            try:
                # 使用 after 在主线程中关闭窗口
                self.root.after(0, self._safe_close)
            except:
                pass

    def _safe_close(self):
        """安全关闭窗口"""
        try:
            self.root.quit()
        except:
            pass
        try:
            self.root.destroy()
        except:
            pass


# 全局单例
_angle_window = None


def get_angle_window() -> AngleDisplayWindow:
    """获取全局角度显示窗口单例"""
    global _angle_window
    if _angle_window is None:
        _angle_window = AngleDisplayWindow()
    return _angle_window