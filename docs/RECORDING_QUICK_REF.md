# 📹 数据录制快速参考

## 基本用法

```bash
# 录制 60 秒，带 10 秒倒计时（默认）
python scripts/record_vision_data.py data/my_recording.jsonl --duration 60

# 自定义倒计时（15秒）
python scripts/record_vision_data.py data/my_recording.jsonl --duration 60 --countdown 15

# 无倒计时（立即开始）
python scripts/record_vision_data.py data/my_recording.jsonl --duration 60 --countdown 0

# 无限录制（按 Ctrl+C 停止）
python scripts/record_vision_data.py data/my_recording.jsonl
```

## 倒计时功能

录制工具默认有 **10 秒倒计时**，让你有时间：
1. 从电脑前走到摄像头视野内
2. 调整站位
3. 确认手臂在视野内
4. 准备开始操作

倒计时结束后会自动开始录制。

## 回放数据

```bash
# 基本回放
python scripts/playback_vision_data.py data/my_recording.jsonl

# 循环回放
python scripts/playback_vision_data.py data/my_recording.jsonl --loop

# 2倍速回放
python scripts/playback_vision_data.py data/my_recording.jsonl --speed 2.0
```

## 完整工作流程

```bash
# 1. 启动视觉节点
python src/nodes/vision_node_depth.py

# 2. 录制数据（另一个终端）
python scripts/record_vision_data.py data/test.jsonl --duration 60

# 3. 在仿真中验证
python scripts/simulate_full_flow.py &
python scripts/playback_vision_data.py data/test.jsonl

# 4. 真机部署
python scripts/run_real_robot_vist_refactored.py --duration 60
```

## 常用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--duration` | 录制时长（秒） | 无限 |
| `--countdown` | 倒计时（秒） | 10 |
| `--ip` | UDP 监听 IP | 从配置读取 |
| `--port` | UDP 监听端口 | 从配置读取 |

## 提示

- ✅ 录制前确保视觉节点正在运行
- ✅ 利用倒计时走到摄像头前
- ✅ 确保手臂始终在视野内
- ✅ 动作要自然、平滑
- ✅ 避免过快或过慢的运动

---

**更多信息**: 查看 [DATA_RECORDING_GUIDE.md](DATA_RECORDING_GUIDE.md)