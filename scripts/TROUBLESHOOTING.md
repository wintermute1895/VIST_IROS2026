# LinkerHand L10 故障排除指南

## 问题：程序运行正常，指令显示成功发出，但手没有反应

### 快速诊断步骤

#### 1. 运行诊断工具

```bash
# 完整诊断
python3 scripts/diagnose_hand.py

# 或者快速检查 CAN 通信
./scripts/monitor_can.sh
```

#### 2. 扫描 CAN ID

如果怀疑 CAN ID 不正确：

```bash
python3 scripts/scan_can_id.py
```

### 常见问题和解决方案

#### 问题 1: CAN ID 不匹配

**症状**：
- 程序显示发送成功
- candump 显示有数据发送
- 但手没有反应

**原因**：
- 代码中配置的 CAN ID (0x27) 与手的硬件 DIP 开关设置不匹配

**解决方法**：

1. 检查手的 DIP 开关设置（通常在手的底部或侧面）
2. 使用扫描工具找到正确的 ID：
   ```bash
   python3 scripts/scan_can_id.py
   ```
3. 修改配置文件 `scripts/hand_control.py`：
   ```python
   class HardwareConfig:
       CAN_ID: int = 0x27  # 修改为正确的 ID
   ```

**常见的 CAN ID**：
- `0x01` (1)
- `0x10` (16)
- `0x20` (32)
- `0x27` (39) - 默认值
- `0x30` (48)

#### 问题 2: CAN 接口未正确配置

**症状**：
- 程序启动失败
- 或显示 CAN 错误

**检查方法**：
```bash
# 检查接口状态
ip link show can0

# 应该看到 "UP" 状态
```

**解决方法**：
```bash
# 启动 CAN 接口
sudo ip link set can0 down
sudo ip link set can0 up type can bitrate 1000000

# 验证
ip -details link show can0
```

#### 问题 3: 硬件连接问题

**检查清单**：

1. **电源**：
   - [ ] 手的电源是否接通
   - [ ] 电源指示灯是否亮起
   - [ ] 电压是否正确（通常 12V 或 24V）

2. **CAN 线连接**：
   - [ ] CAN_H 和 CAN_L 是否正确连接
   - [ ] 线序是否正确（不要接反）
   - [ ] 连接是否牢固

3. **CAN 终端电阻**：
   - [ ] 总线两端是否有 120Ω 终端电阻
   - [ ] 如果是总线末端设备，确保终端电阻已启用

#### 问题 4: 固件未响应

**症状**：
- CAN 数据正常发送
- CAN ID 正确
- 但手仍然不动

**可能原因**：
1. 手的固件处于错误状态
2. 需要发送特定的使能命令
3. 手需要重启

**解决方法**：

1. **重启手的电源**：
   - 断电 5 秒
   - 重新上电
   - 等待初始化完成（通常有指示灯闪烁）

2. **检查固件版本**：
   ```bash
   python3 scripts/diagnose_hand.py
   ```
   查看是否能获取固件版本

3. **尝试发送复位命令**：
   ```python
   # 在 Python 中
   from core.can.linker_hand_l10_can import LinkerHandL10Can
   hand = LinkerHandL10Can(can_id=0x27, can_channel='can0')
   hand.set_joint_positions([0.0] * 10)
   ```

#### 问题 5: 数据格式错误

**检查数据格式**：

使用 candump 监控实际发送的数据：

```bash
candump can0
```

**正确的数据格式应该是**：
```
can0  027  [7]  01 XX XX XX XX XX XX  <- 前 6 个关节 (帧类型 0x01)
can0  027  [5]  04 XX XX XX XX        <- 后 4 个关节 (帧类型 0x04)
```

其中：
- `027` 是 CAN ID (0x27)
- `01` 和 `04` 是帧类型
- `XX` 是关节角度值 (0-255)

### 调试工具

#### 1. 监控 CAN 数据

```bash
# 实时监控
candump can0

# 保存到文件
candump can0 -l

# 过滤特定 ID
candump can0,027:7FF
```

#### 2. 手动发送 CAN 数据

测试硬件是否响应：

```bash
# 发送前 6 个关节的命令 (全 255)
cansend can0 027#01FFFFFFFFFFFF

# 发送后 4 个关节的命令 (全 255)
cansend can0 027#04FFFFFFFF

# 发送复位命令 (全 0)
cansend can0 027#0100000000000000
cansend can0 027#0400000000
```

如果手动发送有反应，说明硬件正常，问题在软件层面。

#### 3. 检查 CAN 错误

```bash
# 查看 CAN 错误统计
ip -s link show can0

# 查看系统日志
dmesg | grep can
```

### 高级调试

#### 启用详细日志

修改 `hand_control.py`：

```python
class LogConfig:
    LOG_LEVEL: str = 'DEBUG'  # 改为 DEBUG
```

#### 禁用过滤

修改 `hand_control.py`：

```python
class HardwareConfig:
    ENABLE_FILTERING: bool = False  # 禁用过滤，确保每次都发送
```

#### 增加延迟

如果怀疑发送太快，修改 `hand_driver.py`：

```python
INTER_FRAME_DELAY = 0.005  # 增加到 5ms
```

### 联系支持

如果以上方法都无法解决问题，请收集以下信息：

1. **硬件信息**：
   - 手的型号和序列号
   - 固件版本（如果能获取）
   - DIP 开关设置

2. **CAN 配置**：
   ```bash
   ip -details link show can0 > can_config.txt
   ifconfig can0 >> can_config.txt
   ```

3. **CAN 数据日志**：
   ```bash
   candump can0 -l
   # 运行程序，然后停止
   # 保存生成的 .log 文件
   ```

4. **程序日志**：
   ```bash
   python3 scripts/hand_control.py --mock 2>&1 | tee hand_control.log
   ```

5. **诊断结果**：
   ```bash
   python3 scripts/diagnose_hand.py 2>&1 | tee diagnose.log
   ```

### 快速参考

| 问题 | 命令 | 预期结果 |
|------|------|----------|
| 检查 CAN 接口 | `ip link show can0` | 显示 UP 状态 |
| 检查波特率 | `ip -details link show can0` | bitrate 1000000 |
| 监控数据 | `candump can0` | 看到 027 开头的数据 |
| 扫描 ID | `python3 scripts/scan_can_id.py` | 找到工作的 ID |
| 完整诊断 | `python3 scripts/diagnose_hand.py` | 逐步检查所有问题 |

### 成功案例

**案例 1: CAN ID 不匹配**
- 问题：手不动
- 解决：运行 `scan_can_id.py`，发现实际 ID 是 0x01
- 修改配置后正常工作

**案例 2: 终端电阻未配置**
- 问题：数据发送但不稳定
- 解决：在 CAN 总线两端添加 120Ω 电阻

**案例 3: 电源问题**
- 问题：手偶尔响应
- 解决：更换电源适配器，确保电流充足

### 预防措施

1. **每次启动前检查**：
   ```bash
   ./scripts/monitor_can.sh
   ```

2. **定期验证配置**：
   ```bash
   python3 scripts/diagnose_hand.py
   ```

3. **保持日志**：
   - 记录工作的配置
   - 保存成功的 CAN ID
   - 记录任何修改

---

**最后更新**: 2026-02-26
**版本**: 1.0