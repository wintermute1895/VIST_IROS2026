# Phase 2 实施指南：视觉节点简化

## 目标
让视觉节点只负责数据采集和预处理，不做坐标系转换。

## 修改清单

### 文件：`src/nodes/vision_node_depth.py`

#### 1. 添加配置导入（在文件开头）
```python
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import get_config
```

#### 2. 修改 `__init__()` 方法
**位置**: Line 22-33

**修改前**:
```python
def __init__(self, udp_ip="127.0.0.1", udp_port=6001, scale=1.0,
             width=640, height=480, fps=30):
```

**修改后**:
```python
def __init__(self, udp_ip=None, udp_port=None, scale=None,
             width=None, height=None, fps=None):
    """
    初始化视觉节点（带深度）
    参数可以从配置文件自动加载，也可以手动指定（手动指定优先）
    """
    print("📷 [VisionNodeDepth] 初始化视觉节点...")

    # 加载配置
    config = get_config()

    # 使用配置文件参数（如果未手动指定）
    self.udp_ip = udp_ip if udp_ip is not None else config.udp_ip
    self.udp_port = udp_port if udp_port is not None else config.udp_port
    self.scale = scale if scale is not None else config.vision_scale
    self.width = width if width is not None else config.vision_width
    self.height = height if height is not None else config.vision_height
    self.fps = fps if fps is not None else config.vision_fps

    print(f"   配置: {self.width}x{self.height} @ {self.fps}fps")
    print(f"   UDP: {self.udp_ip}:{self.udp_port}")
```

#### 3. 简化 `mediapipe_to_robot_coords()` 方法
**位置**: Line 130-169

**修改前**: 方法名 `mediapipe_to_robot_coords`，包含坐标旋转转换

**修改后**: 改名为 `mediapipe_to_shoulder_coords`，移除旋转转换

```python
def mediapipe_to_shoulder_coords(self, mp_point, real_depth=None):
    """
    将 MediaPipe 坐标转换为肩膀坐标系（只做深度融合，不做旋转转换）

    输入：MediaPipe 世界坐标 [x, y, z]
    输出：肩膀坐标系 [x, y, z]
        - X: 向上（垂直）
        - Y: 向右（水平）
        - Z: 向前（靠近相机）
        - 原点：肩部（动态归零）

    注意：本方法不做坐标系旋转转换，转换由 motion_mapper 负责
    """
    x_mp, y_mp, z_mp = mp_point

    # 如果提供了真实深度，替换 Z 坐标
    if real_depth is not None:
        # 关键修正：Z 轴正方向是"靠近相机"
        # real_depth 是相对深度（wrist_depth - shoulder_depth）
        # 向前伸手 → wrist_depth < shoulder_depth → real_depth < 0
        # 但我们希望 Z 增大，所以需要取反
        z_mp = -real_depth

    # 直接返回，不做旋转转换
    # MediaPipe 坐标系 → 肩膀坐标系的映射：
    # - X_shoulder = -Y_mp (向上)
    # - Y_shoulder = X_mp (向右)
    # - Z_shoulder = Z_mp (向前)
    return np.array([
        -y_mp * self.scale,  # X: 向上
        x_mp * self.scale,   # Y: 向右
        z_mp * self.scale    # Z: 向前
    ])
```

#### 4. 更新方法调用
**位置**: Line 281-284

**修改前**:
```python
elbow_robot = self.mediapipe_to_robot_coords(elbow_local_mp, elbow_rel_depth)
wrist_robot = self.mediapipe_to_robot_coords(wrist_local_mp, wrist_rel_depth)
index_robot = self.mediapipe_to_robot_coords(index_local_mp, index_rel_depth)
pinky_robot = self.mediapipe_to_robot_coords(pinky_local_mp, pinky_rel_depth)
```

**修改后**:
```python
elbow_shoulder = self.mediapipe_to_shoulder_coords(elbow_local_mp, elbow_rel_depth)
wrist_shoulder = self.mediapipe_to_shoulder_coords(wrist_local_mp, wrist_rel_depth)
index_shoulder = self.mediapipe_to_shoulder_coords(index_local_mp, index_rel_depth)
pinky_shoulder = self.mediapipe_to_shoulder_coords(pinky_local_mp, pinky_rel_depth)
```

#### 5. 更新 keypoints 字典
**位置**: Line 287-293

**修改前**:
```python
keypoints = {
    'shoulder': shoulder_robot.tolist(),
    'elbow': elbow_robot.tolist(),
    'wrist': wrist_robot.tolist(),
    'index_mcp': index_robot.tolist(),
    'pinky_mcp': pinky_robot.tolist()
}
```

**修改后**:
```python
keypoints = {
    'shoulder': shoulder_shoulder.tolist(),  # [0, 0, 0]
    'elbow': elbow_shoulder.tolist(),
    'wrist': wrist_shoulder.tolist(),
    'index_mcp': index_shoulder.tolist(),
    'pinky_mcp': pinky_shoulder.tolist()
}
```

#### 6. 移除调试代码
删除以下调试相关代码：
- Line 163-170: `_debug_counter` 相关代码
- Line 281-288: `_depth_debug_counter` 相关代码

#### 7. 更新注释
在文件开头的 docstring 中更新说明：
```python
"""
Vision Node with RealSense Depth Integration

职责：
1. 数据采集：MediaPipe 姿态检测 + RealSense 深度
2. 动态归零：以肩部为原点
3. 深度融合：用 RealSense 深度替换 MediaPipe 的 Z 坐标
4. 输出：肩膀坐标系（X=上, Y=右, Z=前）

注意：本节点不做坐标系转换，只输出原始数据
"""
```

## 验证步骤

### 1. 测试配置加载
```bash
python3 -c "from src.config import get_config; config = get_config(); print(config.vision_width)"
# 应该输出: 640
```

### 2. 测试视觉节点
```bash
python3 scripts/test_coordinate_display.py
```

检查：
- 配置是否正确加载
- 坐标显示是否正常
- UDP 数据是否正确发送

### 3. 测试完整流程
```bash
python3 scripts/vist_teleoperation.py
```

检查：
- 向前伸手 → Z 坐标增大
- 机器人向前移动（X 增大）

## 预期效果

### 修改前
- 视觉节点：输出"机器人坐标系"（已转换）
- 映射节点：再次转换（双重转换，容易出错）

### 修改后
- 视觉节点：输出"肩膀坐标系"（未转换）
- 映射节点：负责转换（单一职责，清晰明确）

## 回滚方案

如果出现问题，可以回滚到上一个提交：
```bash
git log --oneline -5  # 查看最近的提交
git revert HEAD       # 回滚最后一次提交
```

## 下一步

完成 Phase 2 后，继续 Phase 3：映射节点职责明确
