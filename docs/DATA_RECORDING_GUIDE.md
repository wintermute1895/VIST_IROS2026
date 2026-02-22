# 📹 数据录制与离线回放指南

## 概述

数据录制与离线回放是机器人算法开发的**核心工具**，可以将开发效率提升 10 倍以上。

### 为什么需要数据录制？

1. **可重复性**：固定的输入数据，可以定量评估算法改进
2. **并行开发**：算法工程师可以在任何地方调试，不占用硬件
3. **消融实验**：论文需要对比不同参数配置的效果
4. **效率提升**：不需要每次调参都让人站在摄像头前

---

## 工具说明

### 1. 录制工具 (`record_vision_data.py`)

监听 UDP 数据流，带时间戳保存到文件。

**功能**：
- 实时监听视觉节点的 UDP 输出
- 保存为 JSONL 格式（每行一个 JSON 对象）
- 支持指定录制时长
- 实时显示录制统计

### 2. 回放工具 (`playback_vision_data.py`)

读取录制的数据文件，按照原始时间戳回放 UDP 数据。

**功能**：
- 按照原始时间戳精确回放
- 支持加速/减速回放（例如 2x 速度）
- 支持循环播放（用于长时间测试）
- 支持从指定帧开始播放

---

## 快速开始

### Step 1: 录制标准测试数据

```bash
# 终端 1: 启动视觉节点
cd /home/ilex/Dev/VIST
python src/nodes/vision_node_depth.py

# 终端 2: 启动录制工具（带10秒倒计时）
python scripts/record_vision_data.py data/test_sequence_001.jsonl --duration 60 --countdown 10

# 倒计时期间（10秒）：
# 1. 从电脑前走到摄像头视野内
# 2. 调整站位，确保身体在摄像头中心
# 3. 确认手臂在摄像头视野内
# 4. 准备开始操作

# 倒计时结束后自动开始录制
# 录制 60 秒后自动停止
```

**倒计时说明**：
- 默认倒计时 10 秒，给你足够时间走到摄像头前
- 可以通过 `--countdown` 参数调整（例如 `--countdown 15`）
- 如果不需要倒计时，设置 `--countdown 0`

**建议录制的标准动作序列**：
1. **慢速插拔**：慢速、平滑的插拔动作（用于测试基本功能）
2. **快速插拔**：快速、敏捷的插拔动作（用于测试速度限制）
3. **复杂轨迹**：包含多个方向变化的复杂动作（用于测试鲁棒性）
4. **静止保持**：手保持静止（用于测试稳定性）

### Step 2: 离线回放测试

```bash
# 终端 1: 启动控制器（不启动视觉节点）
cd /home/ilex/Dev/VIST
python scripts/run_real_robot_vist_refactored.py --duration 120

# 终端 2: 回放录制的数据
python scripts/playback_vision_data.py data/test_sequence_001.jsonl

# 控制器会接收回放的数据，就像视觉节点在实时运行一样
```

### Step 3: 循环播放（用于长时间测试）

```bash
# 循环播放，用于测试系统稳定性
python scripts/playback_vision_data.py data/test_sequence_001.jsonl --loop

# 按 Ctrl+C 停止
```

---

## 高级用法

### 1. 加速/减速回放

```bash
# 2 倍速回放（用于快速测试）
python scripts/playback_vision_data.py data/test_sequence_001.jsonl --speed 2.0

# 0.5 倍速回放（用于慢动作分析）
python scripts/playback_vision_data.py data/test_sequence_001.jsonl --speed 0.5
```

### 2. 从指定帧开始播放

```bash
# 跳过前 100 帧，从第 101 帧开始播放
python scripts/playback_vision_data.py data/test_sequence_001.jsonl --start 100
```

### 3. 自定义 UDP 地址

```bash
# 录制时指定监听地址
python scripts/record_vision_data.py data/test.jsonl --ip 127.0.0.1 --port 5005

# 回放时指定目标地址
python scripts/playback_vision_data.py data/test.jsonl --ip 127.0.0.1 --port 5005
```

---

## 消融实验工作流

### 场景：对比不同的卡尔曼滤波参数

#### Step 1: 录制标准测试数据

```bash
# 录制一组标准的插拔动作
python scripts/record_vision_data.py data/ablation_standard.jsonl --duration 60
```

#### Step 2: 准备不同的配置文件

```bash
# 复制配置文件
cp config/system_config.yaml config/ablation_q_high.yaml
cp config/system_config.yaml config/ablation_q_low.yaml

# 编辑配置文件，修改过程噪声 Q
# ablation_q_high.yaml: 增大 Q（更信任观测）
# ablation_q_low.yaml: 减小 Q（更信任模型）
```

#### Step 3: 运行消融实验

```bash
# 实验 1: 高过程噪声
export VIST_CONFIG=config/ablation_q_high.yaml
python scripts/run_real_robot_vist_refactored.py --duration 120 &
sleep 2
python scripts/playback_vision_data.py data/ablation_standard.jsonl

# 实验 2: 低过程噪声
export VIST_CONFIG=config/ablation_q_low.yaml
python scripts/run_real_robot_vist_refactored.py --duration 120 &
sleep 2
python scripts/playback_vision_data.py data/ablation_standard.jsonl

# 对比性能日志
diff logs/performance_*.json
```

#### Step 4: 分析结果

```bash
# 查看性能指标
cat logs/performance_*.json | jq '.tracking_error'
cat logs/performance_*.json | jq '.smoothness'
```

---

## 数据管理建议

### 目录结构

```
data/
├── recordings/
│   ├── standard_slow.jsonl      # 标准慢速动作
│   ├── standard_fast.jsonl      # 标准快速动作
│   ├── complex_trajectory.jsonl # 复杂轨迹
│   └── static_hold.jsonl        # 静止保持
├── ablation/
│   ├── baseline.jsonl           # 基线数据
│   ├── experiment_001.jsonl     # 实验 1
│   └── experiment_002.jsonl     # 实验 2
└── debug/
    └── issue_*.jsonl            # 调试数据
```

### 命名规范

```
<类型>_<描述>_<日期>.jsonl

例如：
- standard_slow_20260222.jsonl
- ablation_kalman_q_20260222.jsonl
- debug_velocity_limit_20260222.jsonl
```

---

## 常见问题

### Q1: 录制的数据文件很大怎么办？

**A**: JSONL 格式是文本格式，可以压缩：

```bash
# 压缩
gzip data/test_sequence_001.jsonl

# 回放时自动解压
python scripts/playback_vision_data.py data/test_sequence_001.jsonl.gz
```

### Q2: 如何查看录制的数据内容？

**A**: 使用 `jq` 工具查看：

```bash
# 查看第一帧
head -n 1 data/test_sequence_001.jsonl | jq .

# 查看总帧数
wc -l data/test_sequence_001.jsonl

# 查看时间范围
head -n 1 data/test_sequence_001.jsonl | jq .timestamp
tail -n 1 data/test_sequence_001.jsonl | jq .timestamp
```

### Q3: 回放时控制器没有响应？

**A**: 检查以下几点：

1. 控制器是否正在运行并监听 UDP？
2. UDP 地址和端口是否匹配？
3. 防火墙是否阻止了 UDP 通信？

```bash
# 测试 UDP 连接
nc -u -l 5005  # 监听
nc -u 127.0.0.1 5005  # 发送
```

### Q4: 如何验证回放的时间精度？

**A**: 在回放工具中添加日志：

```python
# 在 playback_vision_data.py 中添加
print(f"目标时间: {target_time:.4f}s, 实际时间: {elapsed:.4f}s, 误差: {(elapsed - target_time)*1000:.1f}ms")
```

---

## 性能优化建议

### 1. 减少文件大小

如果数据文件太大，可以：
- 降低录制帧率（在视觉节点中配置）
- 只保存必要的字段（修改录制工具）
- 使用二进制格式（例如 pickle 或 msgpack）

### 2. 提高回放精度

如果回放时间不准确，可以：
- 使用更精确的时间测量（`time.perf_counter()`）
- 减少其他进程的干扰（关闭不必要的程序）
- 使用实时调度优先级（需要 root 权限）

---

## 实战案例

### 案例 1: 调试速度限制问题

**问题**：系统 100% 触发速度限制

**步骤**：
1. 录制一组标准动作
2. 回放数据，观察速度限制触发情况
3. 修改 `max_joint_velocity` 参数
4. 再次回放，对比结果
5. 重复步骤 3-4，直到找到最优参数

**优势**：
- 输入数据完全一致，可以定量对比
- 不需要每次都让人站在摄像头前
- 可以快速迭代（2x 速度回放）

### 案例 2: 卡尔曼滤波参数调优

**问题**：需要找到最优的过程噪声 Q 和观测噪声 R

**步骤**：
1. 录制一组包含快速和慢速动作的数据
2. 准备 10 组不同的 Q/R 参数配置
3. 使用回放工具依次测试每组配置
4. 对比跟踪误差、平滑度等指标
5. 选择最优配置

**优势**：
- 可以在任何地方进行（不需要硬件）
- 可以并行测试（多台电脑同时运行）
- 结果完全可重复

---

## 总结

数据录制与离线回放是机器人算法开发的**必备工具**，可以：

✅ 提升开发效率 10 倍以上
✅ 实现可重复的实验结果
✅ 支持并行开发和消融实验
✅ 降低硬件占用和人力成本

**建议**：
1. 在项目初期就录制一组标准测试数据
2. 每次发现 bug 时录制复现数据
3. 定期更新测试数据集
4. 将数据文件纳入版本控制（使用 Git LFS）

---

**相关文件**：
- [record_vision_data.py](../scripts/record_vision_data.py) - 录制工具
- [playback_vision_data.py](../scripts/playback_vision_data.py) - 回放工具
- [CRITICAL_BUG_ANALYSIS.md](CRITICAL_BUG_ANALYSIS.md) - 时间步长问题分析

**作者**: VIST Project
**日期**: 2026-02-22