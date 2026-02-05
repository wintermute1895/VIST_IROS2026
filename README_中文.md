# VIST - 基于视觉的机械手控制系统

## ✅ 已完成的工作

我已经为你的LinkerHand L10机械手创建了一个完整的基于视觉的控制系统。以下是创建的文件：

### 📁 新建文件

1. **[src/core/vision_controller.py](src/core/vision_controller.py)** (409行)
   - MediaPipe手部追踪集成
   - 几何捏合比率计算（归一化，尺度无关）
   - 3状态机（IDLE → PRE_GRASP → GRASP）
   - 5帧防抖，实现平滑转换
   - 预设关节角度数组（等待你填入）
   - 全面的可视化

2. **[scripts/run_hand.py](scripts/run_hand.py)** (387行)
   - 主入口，正确处理sys.path
   - 集成摄像头、视觉控制器和硬件驱动
   - 带多个选项的命令行界面
   - 实时可视化
   - 退出时安全清理

3. **[src/core/__init__.py](src/core/__init__.py)**
   - 包初始化
   - 导出VisionController和HandState

4. **[设置指南.md](设置指南.md)**
   - 全面的中文文档
   - 架构概述
   - 使用说明
   - 故障排除指南

5. **[关节角度配置.md](关节角度配置.md)**
   - 配置关节角度的快速参考
   - 逐步校准工作流程
   - 示例值

### 🎯 关键特性

**视觉控制器：**
- ✅ MediaPipe手部检测
- ✅ 归一化捏合比率（尺度无关）
- ✅ 带防抖的状态机
- ✅ 三个预设姿态（IDLE、PRE_GRASP、GRASP）
- ✅ 类型提示和全面的文档字符串

**主入口：**
- ✅ 正确的Python路径处理
- ✅ 命令行参数（模拟模式、摄像头ID等）
- ✅ 实时可视化
- ✅ 键盘控制（q=退出、r=重置、s=状态）
- ✅ 安全清理

### 📋 你需要做的下一步

1. **填入关节角度** 在 [src/core/vision_controller.py](src/core/vision_controller.py) 的第30-80行：
   - 三个数组目前都设为0.0
   - 你需要测试并填入适当的值

2. **先在模拟模式下测试：**
   ```bash
   cd /home/luka/.ssh/VIST
   python scripts/run_hand.py --mock
   ```

3. **校准关节角度** 使用驱动测试脚本

4. **使用真实硬件运行：**
   ```bash
   python scripts/run_hand.py
   ```

### 🔑 重要说明

- **关节顺序**：[拇指俯仰, 拇指偏航, 食指, 中指, 无名指, 小指, 食指侧摆, 无名指侧摆, 小指侧摆, 拇指侧摆]
- **单位**：度（不是弧度） - 驱动期望度数
- **捏合比率阈值**：IDLE > 0.8，GRASP ≤ 0.2，PRE_GRASP在中间
- **防抖**：状态切换需要连续5帧

所有代码都遵循你的要求，使用了正确的类型提示、全面的中文注释和清晰的结构。预设关节角度数组显著地放在VisionController类的顶部，方便修改。

## 🚀 快速开始

```bash
# 在模拟模式下测试（无硬件）
cd /home/luka/.ssh/VIST
python scripts/run_hand.py --mock

# 使用真实硬件
python scripts/run_hand.py

# 查看所有选项
python scripts/run_hand.py --help
```

## 📚 文档

- **[设置指南.md](设置指南.md)** - 完整的系统文档
- **[关节角度配置.md](关节角度配置.md)** - 配置关节角度的快速指南

## 🎮 控制键

- **'q'** - 退出
- **'r'** - 重置机械手到零位
- **'s'** - 打印系统状态

---

**创建时间**：2026-02-05
**作者**：Claude (Anthropic)
**项目**：VIST - 基于视觉的手部控制
