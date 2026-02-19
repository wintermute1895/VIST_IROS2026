"""
机器人可视化模块
提供 MeshCat 可视化功能（可选）
"""

import numpy as np
from typing import Optional


class RobotVisualizer:
    """机器人可视化器（可选功能）"""

    def __init__(self, model, collision_model, visual_model, enable: bool = True, show_angle_window: bool = True):
        """
        初始化可视化器

        Args:
            model: Pinocchio 模型
            collision_model: 碰撞模型
            visual_model: 视觉模型
            enable: 是否启用可视化
            show_angle_window: 是否显示角度调试窗口
        """
        self.model = model
        self.collision_model = collision_model
        self.visual_model = visual_model
        self.enable = enable
        self.vis = None
        self.robot_viz = None
        self.show_angle_window = show_angle_window
        self.angle_window = None

        if enable:
            self._init_visualizer()

        # 初始化角度显示窗口
        if show_angle_window:
            try:
                from src.utils.angle_display_window import get_angle_window
                self.angle_window = get_angle_window()
                self.angle_window.start()
                print("✅ [Visualizer] 角度显示窗口已启动")
            except Exception as e:
                print(f"⚠️ [Visualizer] 角度显示窗口启动失败: {e}")
                self.angle_window = None

    def _init_visualizer(self):
        """初始化 MeshCat 可视化器"""
        try:
            import meshcat
            from pinocchio.visualize import MeshcatVisualizer

            self.vis = meshcat.Visualizer()
            print(f"✅ [Visualizer] MeshCat 服务器启动: {self.vis.url()}")

            self.robot_viz = MeshcatVisualizer(
                self.model,
                self.collision_model,
                self.visual_model
            )
            self.robot_viz.initViewer(viewer=self.vis)
            self.robot_viz.loadViewerModel(rootNodeName="robot")
            print("✅ [Visualizer] 机器人模型加载成功")

        except Exception as e:
            print(f"⚠️ [Visualizer] 初始化失败: {e}")
            print("   继续运行但不显示可视化")
            self.enable = False

    def update(self, q: np.ndarray, debug_info: Optional[dict] = None):
        """
        更新机器人显示

        Args:
            q: 关节角度
            debug_info: 调试信息字典（可选），可包含：
                - 'elbow_angle_motor': 电机角度（度）
                - 'elbow_angle_human': 人体肘部角度（度）
                - 'vector_angle': 向量夹角（度）
        """
        if self.enable and self.robot_viz is not None:
            try:
                self.robot_viz.display(q)

                # 显示调试信息
                if debug_info is not None:
                    self._display_debug_info(debug_info)

            except Exception as e:
                print(f"⚠️ [Visualizer] 更新失败: {e}")

    def _display_debug_info(self, debug_info: dict):
        """
        显示调试信息（在独立窗口中）

        Args:
            debug_info: 调试信息字典
        """
        # 更新角度显示窗口
        if self.angle_window is not None:
            self.angle_window.update(debug_info)

    def render(self, viz_data: dict):
        """
        渲染可视化数据（用于多线程控制器）

        Args:
            viz_data: 包含 'q' 和 'debug_info' 的字典
        """
        if not self.enable:
            return

        q = viz_data.get('q')
        debug_info = viz_data.get('debug_info', {})

        if q is not None:
            self.update(q, debug_info)

    def get_url(self) -> Optional[str]:
        """获取 MeshCat 服务器 URL"""
        if self.vis is not None:
            return self.vis.url()
        return None

    def close(self):
        """关闭可视化器"""
        if self.vis is not None:
            self.vis.delete()
            print("✅ [Visualizer] 可视化器已关闭")

        # 关闭角度显示窗口
        if self.angle_window is not None:
            self.angle_window.stop()
            print("✅ [Visualizer] 角度显示窗口已关闭")
