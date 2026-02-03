# VIST 快速启动指南

## 系统架构

```
摄像头 → Vision Node → UDP → Arm Node → IK Solver → Robot Driver → MeshCat
         (MediaPipe)         (Mapper)    (6-DoF)     (Mock/Real)   (可视化)
```

## 前置要求

### 1. 安装依赖

```bash
# 核心依赖
pip install numpy scipy pinocchio

# 视觉依赖
pip install mediapipe opencv-python

# 可视化依赖
pip install meshcat
```

### 2. 硬件要求

- 摄像头（USB 或内置）
- 推荐：光线充足的环境

## 运行方式

### 方式 1: 完整系统集成（推荐）

同时运行视觉节点和手臂控制节点：

```bash
python test_vision_integration.py
```

**窗口说明:**
- **OpenCV 窗口**: 显示摄像头画面和手部检测
- **MeshCat 窗口**: 在浏览器中显示机器人 3D 模型（自动打开）

**操作:**
1. 将手放在摄像头前
2. 移动手部控制机械臂
3. 按 'q' 或 ESC 退出视觉窗口
4. 按 Ctrl+C 停止整个系统

### 方式 2: 分别运行（调试用）

**终端 1 - 启动 Arm Node:**
```bash
python -m src.nodes.arm_node
```

**终端 2 - 启动 Vision Node:**
```bash
python -m src.nodes.vision_node
```

### 方式 3: 仅测试 IK（无摄像头）

使用 Mock 数据测试 IK 求解器：

```bash
python test_ik_integration.py
```

## 系统组件说明

### 1. Vision Node (视觉节点)
- **文件**: `src/nodes/vision_node.py`
- **功能**: MediaPipe Hands 手部检测
- **输出**: UDP 发送关键点数据（端口 6001）
- **可视化**: OpenCV 窗口显示手部骨架

### 2. Arm Node (手臂控制节点)
- **文件**: `src/nodes/arm_node.py`
- **功能**: 接收关键点 → 运动映射 → IK 求解 → 机器人控制
- **输入**: UDP 接收关键点数据（端口 6001）
- **可视化**: MeshCat 显示机器人姿态

### 3. Motion Mapper (运动映射器)
- **文件**: `src/core/motion_mapper.py`
- **功能**: 人体关键点 → 机器人目标位姿（位置 + 姿态）
- **创新**: 使用指关节向量计算手部姿态

### 4. IK Solver (逆运动学求解器)
- **文件**: `src/core/ik_solver.py`
- **功能**: 6-DoF 姿态追踪（位置 + 旋转）
- **算法**: CLIK + Damped Least Squares
- **性能**: 位置误差 < 5mm，旋转误差 < 1°

## 参数调整

### 灵敏度调整

修改 `test_vision_integration.py` 中的 `scale` 参数：

```python
node = VisionNode(
    camera_id=0,
    scale=1.5  # 增加灵敏度（默认 1.0）
)
```

### IK 权重调整

修改 `src/nodes/arm_node.py` 中的权重参数：

```python
q_solution, success, ik_error = self.ik_solver.solve(
    target_pos,
    target_quat=target_quat,
    pos_weight=1.0,  # 位置权重
    rot_weight=0.5   # 旋转权重（姿态次于位置）
)
```

### 控制频率调整

修改 `src/nodes/arm_node.py` 的运行频率：

```python
node.run(frequency=50)  # 50 Hz（默认）
```

## 性能指标

| 指标 | 目标值 | 实际值 |
|------|--------|--------|
| Vision Node FPS | 30+ | 30-60 |
| Arm Node 频率 | 50 Hz | 50 Hz |
| IK 位置误差 | < 5mm | 2-5mm |
| IK 旋转误差 | < 1° | 0.3-1° |
| IK 迭代次数 | < 50 | 20-100 |
| 端到端延迟 | < 50ms | 30-50ms |

## 故障排除

### 问题 1: 摄像头无法打开
```
RuntimeError: 无法打开摄像头 0
```

**解决方案:**
- 检查摄像头是否被其他程序占用
- 尝试修改 `camera_id` 参数（0, 1, 2...）
- Linux: 检查权限 `ls -l /dev/video*`

### 问题 2: MeshCat 无法显示
```
⚠️ [ArmNode] 可视化器初始化失败
```

**解决方案:**
- 检查 meshcat 是否正确安装
- 尝试手动打开浏览器访问 `http://127.0.0.1:7000/static/`
- 如果不需要可视化，设置 `visualize=False`

### 问题 3: UDP 数据未接收
```
⚠️ [ArmNode] 收到的数据格式不正确
```

**解决方案:**
- 确保 Vision Node 和 Arm Node 使用相同端口（6001）
- 检查防火墙设置
- 使用 `netstat -an | grep 6001` 检查端口占用

### 问题 4: IK 求解失败
```
⚠️ [IK] 6-DoF 姿态追踪失败
```

**解决方案:**
- 检查目标位置是否在机器人工作空间内
- 增加 `max_iter` 参数
- 放宽 `tol` 参数（例如 `tol=1e-2`）
- 降低 `rot_weight` 参数

## 下一步开发

- [ ] 添加手势识别（抓取、释放）
- [ ] 支持双手协同控制
- [ ] 添加碰撞检测
- [ ] 支持真实机器人硬件
- [ ] 添加力反馈
- [ ] 实现轨迹录制和回放

## 相关文档

- [Vision Node 详细文档](vision_node.md)
- [Motion Mapper 测试报告](motion_mapper_test.md)
- [VIST 建模文档](VIST_modeling.md)

## 技术支持

如有问题，请查看：
1. 代码注释
2. 测试脚本输出
3. 相关文档
