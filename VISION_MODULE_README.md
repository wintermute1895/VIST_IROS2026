# Feature: Vision Perception Module

## 📋 当前状态

✅ **接口设计完成** (2026-02-09)
- 数据契约: VisionPacket, Keypoint3D, TrackingStatus
- 抽象接口: IVisionSystem
- 安全握手层: VisionSafetyLayer
- 完整文档和测试

✅ **分支已同步**
- 已合并 feature/arm-control 的最新代码
- 控制模块（motion_mapper, vist_kalman_filter）已就绪
- 接口测试全部通过

## 🎯 下一步工作

### 1. 实现 MediaPipe 视觉模块

创建文件：`src/vision/mediapipe_vision.py`

```python
from src.interfaces.vision_system import IVisionSystem
from src.interfaces.vision_packet import VisionPacket, Keypoint3D, TrackingStatus
import mediapipe as mp
import numpy as np

class MediaPipeVision(IVisionSystem):
    def __init__(self, camera_type='realsense'):
        # TODO: 初始化 MediaPipe Pose
        # TODO: 初始化相机（RealSense 或 USB）
        pass

    def initialize(self) -> bool:
        # TODO: 初始化硬件和算法
        pass

    def start(self) -> bool:
        # TODO: 启动相机流
        pass

    def get_latest_frame(self, timeout=0.1) -> Optional[VisionPacket]:
        # TODO: 1. 获取相机帧
        # TODO: 2. MediaPipe 检测
        # TODO: 3. 提取关键点
        # TODO: 4. 深度融合（RealSense）
        # TODO: 5. 坐标系转换（相机 → 肩部坐标系）
        # TODO: 6. 构建 VisionPacket
        pass

    def stop(self) -> bool:
        # TODO: 停止相机流
        pass

    def cleanup(self) -> None:
        # TODO: 清理资源
        pass

    def is_running(self) -> bool:
        return self._running

    def get_fps(self) -> float:
        return self._fps

    def get_algorithm_name(self) -> str:
        return "MediaPipe"
```

### 2. 集成测试

修改 `examples/vision_control_integration.py`：

```python
# 替换 MockVisionSystem 为 MediaPipeVision
from src.vision.mediapipe_vision import MediaPipeVision

vision = MediaPipeVision(camera_type='realsense')
bridge = VisionControlBridge(vision)
# ... 其他代码不变
```

### 3. 端到端测试

运行完整的视觉-控制流程：

```bash
python examples/vision_control_integration.py
```

## 📚 参考文档

- **接口协议**: [docs/vision_control_protocol.md](../docs/vision_control_protocol.md)
- **开发路线图**: [docs/vision_development_roadmap.md](../docs/vision_development_roadmap.md)
- **总结报告**: [docs/vision_interface_summary.md](../docs/vision_interface_summary.md)

## 🧪 测试

运行接口测试：
```bash
python tests/test_vision_interface.py
```

运行集成示例（使用模拟数据）：
```bash
python examples/vision_control_integration.py
```

## 🏗️ 架构

```
视觉模块 (MediaPipe)
    ↓ VisionPacket
安全层 (VisionSafetyLayer)
    ↓ SafetyCheckResult
桥接器 (VisionControlBridge)
    ↓ human_kps
运动映射器 (ArmMotionMapper)
    ↓ target_pos, target_quat
VIST 滤波器 (VISTKalmanFilter)
    ↓ joint_angles
机器人驱动 (RealArmDriver)
```

## 📝 开发检查清单

### 阶段 1: 基础功能（2周）
- [ ] 实现 MediaPipeVision 类
- [ ] 集成 RealSense 深度相机
- [ ] 实现坐标系转换（相机 → 肩部坐标系）
- [ ] 深度融合（2D 关键点 + 深度图 → 3D 坐标）
- [ ] 集成测试（视觉 → 控制 → 机器人）

### 阶段 2: 鲁棒性（2周）
- [ ] 遮挡处理（last_known / extrapolate）
- [ ] 跳变抑制（One Euro Filter）
- [ ] 性能优化（GPU 加速、多线程）
- [ ] 延迟分析（目标 < 100ms）

### 阶段 3: 高级功能（3周）
- [ ] YOLO + DepthAI 实现
- [ ] 算法性能对比
- [ ] 自适应算法切换

## 🔧 依赖安装

```bash
# MediaPipe
pip install mediapipe

# RealSense
pip install pyrealsense2

# OpenCV
pip install opencv-python

# 其他依赖
pip install numpy scipy
```

## 📞 技术支持

如有问题，请参考：
1. 接口文档：`docs/vision_control_protocol.md`
2. 开发路线图：`docs/vision_development_roadmap.md`
3. 示例代码：`examples/vision_control_integration.py`
4. 单元测试：`tests/test_vision_interface.py`

---

**分支**: feature/vision-perception
**状态**: 接口设计完成，准备开发视觉模块
**最后更新**: 2026-02-09
