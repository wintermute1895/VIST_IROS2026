"""
机器人可视化模块
提供 MeshCat 可视化功能（可选）
"""

import numpy as np
from typing import Optional


class RobotVisualizer:
    """机器人可视化器（可选功能）"""

    def __init__(self, model, collision_model, visual_model, enable: bool = True):
        """
        初始化可视化器

        Args:
            model: Pinocchio 模型
            collision_model: 碰撞模型
            visual_model: 视觉模型
            enable: 是否启用可视化
        """
        self.model = model
        self.collision_model = collision_model
        self.visual_model = visual_model
        self.enable = enable
        self.vis = None
        self.robot_viz = None

        if enable:
            self._init_visualizer()

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

    def update(self, q: np.ndarray):
        """
        更新机器人显示

        Args:
            q: 关节角度
        """
        if self.enable and self.robot_viz is not None:
            try:
                self.robot_viz.display(q)
            except Exception as e:
                print(f"⚠️ [Visualizer] 更新失败: {e}")

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
