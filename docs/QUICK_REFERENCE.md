# 🎯 VIST 项目快速参考

## 最新更新 (2026-02-22)

### ✅ 修复：100% 安全限制触发问题

**问题**：系统在真机上 100% 触发速度和加速度限制
**原因**：时间步长不匹配（配置 20Hz vs 实际 17Hz）
**修复**：SafeRobotController 现在测量实际的时间间隔

详见：[CRITICAL_BUG_ANALYSIS.md](docs/CRITICAL_BUG_ANALYSIS.md)

### 🆕 新功能：数据录制与离线回放

**用途**：
- 离线调试控制算法（不需要硬件）
- 消融实验（对比不同参数配置）
- 可重复的性能测试

详见：[DATA_RECORDING_GUIDE.md](docs/DATA_RECORDING_GUIDE.md)

---

## 快速启动

### 1. 真机控制（完整流程）

```bash
# 终端 1: 启动视觉节点
python src/nodes/vision_node_depth.py

# 终端 2: 启动控制器
python scripts/run_real_robot_vist_refactored.py --duration 60
```

### 2. 数据录制与回放

```bash
# 使用交互式工具
./scripts/data_tools.sh

# 或手动执行
python scripts/record_vision_data.py data/test.jsonl --duration 60
python scripts/playback_vision_data.py data/test.jsonl --loop
```

---

## 核心文件说明

### 控制系统

| 文件 | 说明 |
|------|------|
| [safe_robot_controller.py](src/control/safe_robot_controller.py) | 安全控制器（速度/加速度限制）|
| [trajectory_interpolator.py](src/control/trajectory_interpolator.py) | 轨迹插值器（梯形速度曲线）|
| [vist_controller.py](src/control/vist_controller.py) | VIST 主控制器 |
| [run_real_robot_vist_refactored.py](scripts/run_real_robot_vist_refactored.py) | 真机控制主程序 |

### 视觉系统

| 文件 | 说明 |
|------|------|
| [vision_node_depth.py](src/nodes/vision_node_depth.py) | 视觉节点（MediaPipe + RealSense）|

### 数据工具

| 文件 | 说明 |
|------|------|
| [record_vision_data.py](scripts/record_vision_data.py) | 数据录制工具 |
| [playback_vision_data.py](scripts/playback_vision_data.py) | 数据回放工具 |
| [data_tools.sh](scripts/data_tools.sh) | 交互式数据工具 |

### 配置文件

| 文件 | 说明 |
|------|------|
| [system_config.yaml](config/system_config.yaml) | 系统主配置 |

---

## 常见任务

### 调试速度限制问题

```bash
# 1. 录制测试数据
python scripts/record_vision_data.py data/debug_velocity.jsonl --duration 30

# 2. 修改配置文件中的 max_joint_velocity

# 3. 回放测试
python scripts/run_real_robot_vist_refactored.py --duration 60 &
python scripts/playback_vision_data.py data/debug_velocity.jsonl

# 4. 查看性能日志
cat logs/performance_*.json | jq '.safety_controller'
```

### 卡尔曼滤波参数调优

```bash
# 1. 录制标准测试数据
python scripts/record_vision_data.py data/kalman_tuning.jsonl --duration 60

# 2. 准备不同的配置文件
cp config/system_config.yaml config/test_q_high.yaml
# 编辑 test_q_high.yaml，修改 vist_kalman 参数

# 3. 测试不同配置
export VIST_CONFIG=config/test_q_high.yaml
python scripts/run_real_robot_vist_refactored.py --duration 120 &
python scripts/playback_vision_data.py data/kalman_tuning.jsonl

# 4. 对比结果
diff logs/performance_*.json
```

### 消融实验

```bash
# 使用相同的输入数据测试不同的配置
for config in config/ablation_*.yaml; do
    echo "Testing $config"
    export VIST_CONFIG=$config
    python scripts/run_real_robot_vist_refactored.py --duration 120 &
    sleep 2
    python scripts/playback_vision_data.py data/ablation_standard.jsonl
    wait
done
```

---

## 性能监控

### 实时监控

控制器运行时会每秒打印状态：

```
✅ 帧数: 542 | 成功率: 98.5% | 延迟: 4.6ms | 频率: 16.9Hz | 意图: 0.85
```

### 性能日志

运行结束后会生成详细的性能日志：

```bash
# 查看性能摘要
cat logs/performance_20260222_143052.json | jq .

# 查看安全控制统计
cat logs/performance_20260222_143052.json | jq '.safety_controller'

# 查看跟踪误差
cat logs/performance_20260222_143052.json | jq '.tracking_error'
```

---

## 故障排查

### 问题 1: 100% 触发速度限制

**原因**：时间步长不匹配
**解决**：已修复（见 CRITICAL_BUG_ANALYSIS.md）

### 问题 2: 视觉节点无法启动

**检查**：
```bash
# 检查 RealSense 相机
rs-enumerate-devices

# 检查 MediaPipe
python -c "import mediapipe; print(mediapipe.__version__)"
```

### 问题 3: UDP 数据未接收

**检查**：
```bash
# 测试 UDP 连接
nc -u -l 5005  # 监听
nc -u 127.0.0.1 5005  # 发送

# 检查防火墙
sudo ufw status
```

---

## 文档索引

- [CRITICAL_BUG_ANALYSIS.md](docs/CRITICAL_BUG_ANALYSIS.md) - 时间步长问题的深度分析
- [DATA_RECORDING_GUIDE.md](docs/DATA_RECORDING_GUIDE.md) - 数据录制与回放指南
- [PARAMETER_EXPLANATION.md](docs/PARAMETER_EXPLANATION.md) - 参数说明
- [PERFORMANCE_METRICS_GUIDE.py](docs/PERFORMANCE_METRICS_GUIDE.py) - 性能指标说明

---

## 开发建议

### 1. 使用数据录制加速开发

✅ **推荐**：录制标准测试数据，离线调试
❌ **不推荐**：每次调参都开硬件

### 2. 定期检查性能日志

```bash
# 每次运行后检查
cat logs/performance_*.json | jq '.safety_controller'
```

### 3. 使用版本控制管理配置

```bash
# 提交配置变更
git add config/system_config.yaml
git commit -m "feat: 调整速度限制参数"
```

---

## 联系方式

- **项目**: VIST (Vision-based Intent-Driven Manifold Constraint)
- **作者**: VIST Project Team
- **日期**: 2026-02-22

---

**祝你的真机测试顺利！** 🚀