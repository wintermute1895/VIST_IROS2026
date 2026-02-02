import pinocchio as pin
from pinocchio.visualize import MeshcatVisualizer
import meshcat.geometry as g
import meshcat.transformations as tf
import numpy as np
import socket
import json
import time
import os

# ================= 配置 =================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FULL_ROBOT_URDF = os.path.join(CURRENT_DIR, "config/combined_robot/robot.urdf")
FULL_ROBOT_PKG = os.path.join(CURRENT_DIR, "config/combined_robot")
HOST = "127.0.0.1"
PORT = 6000 

class RobotServer:
    def __init__(self):
        print(f"🖥️ 启动机器人显示服务器 (支持可视化调试)...")
        
        # 1. 加载模型
        self.robot = pin.RobotWrapper.BuildFromURDF(FULL_ROBOT_URDF, package_dirs=[FULL_ROBOT_PKG])
        self.model, self.data = self.robot.model, self.robot.data
        self.q = pin.neutral(self.model).copy()
        
        # 2. 启动 Meshcat
        self.viz = MeshcatVisualizer(self.model, self.robot.collision_model, self.robot.visual_model)
        self.viz.initViewer(open=True)
        self.viz.loadViewerModel()
        
        # 3. 初始化调试可视化的物体 (半透明球体和连杆)
        # 材质: 半透明 (opacity=0.5)
        mat_shoulder = g.MeshLambertMaterial(color=0xff0000, opacity=0.5, transparent=True)
        mat_elbow = g.MeshLambertMaterial(color=0x00ff00, opacity=0.5, transparent=True)
        mat_wrist = g.MeshLambertMaterial(color=0x0000ff, opacity=0.5, transparent=True)
        mat_link = g.MeshLambertMaterial(color=0xffff00, opacity=0.3, transparent=True)
        
        # 创建球体
        self.viz.viewer["debug/shoulder"].set_object(g.Sphere(0.05), mat_shoulder)
        self.viz.viewer["debug/elbow"].set_object(g.Sphere(0.04), mat_elbow)
        self.viz.viewer["debug/wrist"].set_object(g.Sphere(0.03), mat_wrist)
        
        # 创建连杆 (初始放个长度1的圆柱，后面动态缩放)
        self.viz.viewer["debug/link_upper"].set_object(g.Cylinder(1.0, 0.02), mat_link)
        self.viz.viewer["debug/link_fore"].set_object(g.Cylinder(1.0, 0.02), mat_link)

        # 4. UDP
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((HOST, PORT))
        self.sock.setblocking(False)

    def update_joints(self, joint_dict):
        for name, angle in joint_dict.items():
            if self.model.existJointName(name):
                idx = self.model.joints[self.model.getJointId(name)].idx_q
                limit_l = self.model.lowerPositionLimit[idx]
                limit_u = self.model.upperPositionLimit[idx]
                self.q[idx] = np.clip(angle, limit_l, limit_u)

    def draw_cylinder_between_points(self, name, p1, p2):
        """在两点之间画圆柱"""
        vec = p2 - p1
        length = np.linalg.norm(vec)
        if length < 1e-3: return

        # Meshcat Cylinder 默认是 Y 轴向的
        # 计算中点
        center = (p1 + p2) / 2.0
        
        # 计算旋转 (将 Y 轴对齐到 vec 方向)
        y_axis = np.array([0, 1, 0])
        vec_normalized = vec / length
        
        # 计算旋转轴和角度
        v = np.cross(y_axis, vec_normalized)
        c = np.dot(y_axis, vec_normalized)
        k = 1.0 / (1.0 + c)
        
        # 构建旋转矩阵 (Rodrigues formula 变体)
        R = np.eye(3) + np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ]) + np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ]) @ np.array([
            [0, -v[2], v[1]],
            [v[2], 0, -v[0]],
            [-v[1], v[0], 0]
        ]) * k

        # 组合变换矩阵
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = center
        
        # 应用变换并缩放长度 (Meshcat Cylinder 默认高度是 1，所以 scale Y 轴即可)
        # 注意：set_transform 设置位置和旋转，set_property 设置 scale
        self.viz.viewer[name].set_transform(T)
        # 这里有个 trick，直接用 transform 缩放 Y 轴会导致圆柱变椭圆
        # 更好的方法是重新生成 Cylinder geometry，但太慢。
        # 我们用简单的 LineSegments 代替圆柱连杆可能更好，但为了圆柱效果，我们容忍一点变形或者仅做位置更新
        # 修正：Meshcat 不支持动态修改 Cylinder 的 height。
        # 替代方案：每次重新 set_object 太慢。
        # 妥协方案：只画球，或者只更新球的位置。连杆用 LineSegments 画比较好。
        
        # 为了不卡顿，我们这里简化：只画球。连杆如果你需要，可以用 LineSegments。
        # 下面演示用 Line 替代 Cylinder 以保证性能
        
    def update_debug_visuals(self, debug_data):
        """
        debug_data: {"s": [x,y,z], "e": [x,y,z], "w": [x,y,z]}
        """
        s = np.array(debug_data['s'])
        e = np.array(debug_data['e'])
        w = np.array(debug_data['w'])
        
        # 更新球体位置
        self.viz.viewer["debug/shoulder"].set_transform(tf.translation_matrix(s))
        self.viz.viewer["debug/elbow"].set_transform(tf.translation_matrix(e))
        self.viz.viewer["debug/wrist"].set_transform(tf.translation_matrix(w))
        
        # 画连杆 (用 LineSegments 更快更简单)
        self.viz.viewer["debug/lines"].set_object(
            g.LineSegments(
                g.PointsGeometry(np.array([s, e, e, w]).T.astype(np.float32)),
                g.MeshBasicMaterial(color=0xffff00, linewidth=5, opacity=0.5, transparent=True)
            )
        )

    def run(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
                packet = json.loads(data.decode())
                
                # 1. 关节控制
                if "joints" in packet:
                    self.update_joints(packet["joints"])
                
                # 2. 调试可视化
                if "debug_viz" in packet:
                    self.update_debug_visuals(packet["debug_viz"])
                    
                self.viz.display(self.q)
                
            except BlockingIOError:
                time.sleep(0.002)
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    RobotServer().run()