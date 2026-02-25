# 进程安全检查和清理工具

**用途**: 启动前必须运行，确保没有残留进程

---

## 快速检查命令

```bash
# 一键检查所有相关进程
ps aux | grep -E "linkerta|lbot|teleop|vist" | grep -v grep
```

**如果有任何输出，说明有残留进程！**

---

## 详细检查

### 1. 检查linkerta进程

```bash
pgrep -af linkerta
```

**预期**: 无输出
**如果有输出**: 记录PID，准备清理

---

### 2. 检查lbot进程

```bash
pgrep -af lbot
```

**预期**: 无输出
**如果有输出**: 记录PID，准备清理

---

### 3. 检查teleop进程

```bash
pgrep -af teleop
```

**预期**: 无输出
**如果有输出**: 记录PID，准备清理

---

### 4. 检查ROS2节点

```bash
# 需要先source ROS2环境
source /opt/ros/humble/setup.bash

# 列出所有ROS2节点
ros2 node list 2>/dev/null
```

**预期**: 无输出或只有系统节点
**如果看到**: `/lbot_driver`, `/linkerta_node`, `/teleop_bridge_node` 等，说明有残留

---

## 安全清理流程

### 方法1: 优雅停止（推荐）

```bash
# 1. 找出所有相关进程
ps aux | grep -E "linkerta|lbot|teleop" | grep -v grep

# 2. 记录PID（假设是12345, 12346, 12347）

# 3. 发送SIGTERM信号（优雅停止）
kill -15 12345
kill -15 12346
kill -15 12347

# 4. 等待3秒
sleep 3

# 5. 检查是否还在运行
pgrep -af linkerta
pgrep -af lbot
pgrep -af teleop
```

---

### 方法2: 强制停止（如果方法1失败）

```bash
# 1. 发送SIGKILL信号（强制杀死）
pkill -9 -f linkerta
pkill -9 -f lbot
pkill -9 -f teleop

# 2. 等待1秒
sleep 1

# 3. 确认清理完成
pgrep -af linkerta
pgrep -af lbot
pgrep -af teleop

# 应该无输出
```

---

## 完整检查脚本（手动执行每一行）

```bash
echo "=========================================="
echo "进程安全检查"
echo "=========================================="
echo ""

echo "1. 检查linkerta进程..."
LINKERTA_COUNT=$(pgrep -af linkerta | wc -l)
if [ $LINKERTA_COUNT -gt 0 ]; then
    echo "⚠️  发现 $LINKERTA_COUNT 个linkerta进程:"
    pgrep -af linkerta
else
    echo "✅ 无linkerta进程"
fi
echo ""

echo "2. 检查lbot进程..."
LBOT_COUNT=$(pgrep -af lbot | wc -l)
if [ $LBOT_COUNT -gt 0 ]; then
    echo "⚠️  发现 $LBOT_COUNT 个lbot进程:"
    pgrep -af lbot
else
    echo "✅ 无lbot进程"
fi
echo ""

echo "3. 检查teleop进程..."
TELEOP_COUNT=$(pgrep -af teleop | wc -l)
if [ $TELEOP_COUNT -gt 0 ]; then
    echo "⚠️  发现 $TELEOP_COUNT 个teleop进程:"
    pgrep -af teleop
else
    echo "✅ 无teleop进程"
fi
echo ""

TOTAL_COUNT=$((LINKERTA_COUNT + LBOT_COUNT + TELEOP_COUNT))

if [ $TOTAL_COUNT -gt 0 ]; then
    echo "=========================================="
    echo "⚠️  发现 $TOTAL_COUNT 个残留进程！"
    echo "=========================================="
    echo ""
    echo "请手动清理这些进程："
    echo "1. 记录上面显示的PID"
    echo "2. 运行: kill -9 <PID>"
    echo "3. 再次运行本检查确认清理完成"
    echo ""
else
    echo "=========================================="
    echo "✅ 所有检查通过，可以安全启动"
    echo "=========================================="
fi
```

---

## 检查ROS2话题（确认没有数据流）

```bash
# Source ROS2环境
source /opt/ros/humble/setup.bash

# 列出所有话题
echo "当前活跃的ROS2话题:"
ros2 topic list 2>/dev/null

# 如果看到以下话题，说明有节点在运行:
# /left_arm_joint_control
# /right_arm_joint_control
# /robot1/right_arm/joint_follow
# /robot1/right_arm/joint_states
```

---

## 检查网络连接（确认机械臂状态）

```bash
# 检查机械臂是否在线
echo "检查机械臂网络连接..."
if ping -c 1 -W 1 192.168.10.21 > /dev/null 2>&1; then
    echo "✅ 机械臂在线 (192.168.10.21)"

    # 检查延迟
    LATENCY=$(ping -c 3 192.168.10.21 | tail -1 | awk -F '/' '{print $5}')
    echo "   平均延迟: ${LATENCY}ms"

    if (( $(echo "$LATENCY > 5" | bc -l) )); then
        echo "⚠️  延迟较高，可能影响控制性能"
    fi
else
    echo "❌ 机械臂离线或网络不通"
fi
```

---

## 检查USB设备（外骨骼连接）

```bash
echo "检查USB设备..."
USB_DEVICES=$(ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null)

if [ -n "$USB_DEVICES" ]; then
    echo "✅ 发现USB设备:"
    echo "$USB_DEVICES"
else
    echo "⚠️  未发现USB设备，外骨骼可能未连接"
fi
```

---

## 完整启动前检查清单

```bash
echo "=========================================="
echo "启动前完整安全检查"
echo "=========================================="
echo ""

# 1. 进程检查
echo "【1/5】进程检查..."
PROCESS_COUNT=$(pgrep -af "linkerta|lbot|teleop" | wc -l)
if [ $PROCESS_COUNT -eq 0 ]; then
    echo "✅ 无残留进程"
else
    echo "❌ 发现 $PROCESS_COUNT 个残留进程，必须清理！"
    pgrep -af "linkerta|lbot|teleop"
    exit 1
fi
echo ""

# 2. 网络检查
echo "【2/5】网络检查..."
if ping -c 1 -W 1 192.168.10.21 > /dev/null 2>&1; then
    echo "✅ 机械臂网络连接正常"
else
    echo "❌ 机械臂网络不通"
    exit 1
fi
echo ""

# 3. USB检查
echo "【3/5】USB设备检查..."
if ls /dev/ttyUSB* /dev/ttyACM* > /dev/null 2>&1; then
    echo "✅ USB设备已连接"
else
    echo "⚠️  未发现USB设备"
fi
echo ""

# 4. ROS2环境检查
echo "【4/5】ROS2环境检查..."
if [ -n "$ROS_DISTRO" ]; then
    echo "✅ ROS2环境已加载 ($ROS_DISTRO)"
else
    echo "⚠️  ROS2环境未加载"
    echo "   请运行: source /opt/ros/humble/setup.bash"
fi
echo ""

# 5. 工作空间检查
echo "【5/5】工作空间检查..."
if [ -f "/home/ilex/Dev/VIST/external_sdk/arm_teleop/install/setup.bash" ]; then
    echo "✅ 工作空间存在"
else
    echo "❌ 工作空间不存在"
    exit 1
fi
echo ""

echo "=========================================="
echo "✅ 所有检查通过，可以安全启动"
echo "=========================================="
echo ""
echo "下一步: 参考 SAFE_MANUAL_OPERATION_GUIDE.md"
echo "        按照手册逐步启动各个节点"
```

---

## 紧急清理命令（谨慎使用）

```bash
# ⚠️ 警告: 这会强制杀死所有相关进程
# 只在紧急情况下使用

echo "执行紧急清理..."

# 杀死所有linkerta进程
pkill -9 -f linkerta
echo "已清理linkerta进程"

# 杀死所有lbot进程
pkill -9 -f lbot
echo "已清理lbot进程"

# 杀死所有teleop进程
pkill -9 -f teleop
echo "已清理teleop进程"

# 等待1秒
sleep 1

# 确认清理完成
echo ""
echo "清理完成，验证结果:"
pgrep -af "linkerta|lbot|teleop"

if [ $? -eq 1 ]; then
    echo "✅ 所有进程已清理"
else
    echo "⚠️  仍有残留进程，请手动检查"
fi
```

---

## 使用方法

### 每次启动前：

1. **打开终端**
2. **复制上面的"完整启动前检查清单"代码**
3. **逐行执行，观察输出**
4. **确认所有检查通过**
5. **然后参考 SAFE_MANUAL_OPERATION_GUIDE.md 启动系统**

### 发现残留进程时：

1. **记录进程PID**
2. **使用 `kill -9 <PID>` 清理**
3. **再次运行检查确认**

### 紧急情况：

1. **Ctrl+C 停止所有终端**
2. **运行紧急清理命令**
3. **检查机械臂状态**
4. **记录日志**

---

## 总结

**每次启动前必须**:
- ✅ 运行进程检查
- ✅ 确认无残留进程
- ✅ 检查网络和硬件
- ✅ 记录检查结果

**绝不**:
- ❌ 跳过检查直接启动
- ❌ 忽略残留进程警告
- ❌ 使用自动化脚本

**记住**: 电机烧毁的教训，安全检查永远不嫌多！
