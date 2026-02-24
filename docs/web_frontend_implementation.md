# VIST Web控制台实现总结

## 已完成的功能

### 1. 后端API服务 (FastAPI)

**文件**: `web/backend/main.py`

**功能**:
- RESTful API端点
- WebSocket实时数据推送
- 系统状态监控
- 相机管理接口
- 性能数据接口
- 数据录制控制
- 配置管理

**API端点**:
- `GET /api/system/status` - 系统状态
- `GET /api/cameras/list` - 相机列表
- `POST /api/cameras/{name}/start` - 启动相机
- `POST /api/cameras/{name}/stop` - 停止相机
- `GET /api/performance/metrics` - 性能指标
- `POST /api/recording/start` - 开始录制
- `POST /api/recording/stop` - 停止录制
- `GET /api/recordings/list` - 录制列表
- `GET /api/config` - 获取配置
- `POST /api/config` - 更新配置
- `WS /ws/realtime` - 实时数据推送

### 2. 前端Web应用 (React + TypeScript)

**技术栈**:
- React 18
- TypeScript
- Vite (构建工具)
- Tailwind CSS (样式)
- Chart.js (图表)
- React Router (路由)
- Lucide React (图标)

**页面模块**:

#### Dashboard (系统监控)
- 实时系统状态卡片
- CPU/内存使用率
- 视觉系统状态
- 机器人连接状态
- 系统信息展示

#### Camera Manager (相机管理)
- 列出所有RealSense相机
- 显示相机详细信息（序列号、型号、分辨率、帧率）
- 启动/停止相机控制
- 实时状态指示

#### Performance Monitor (性能监控)
- 实时性能指标卡片
- 追踪误差图表
- Jerk（平滑度）图表
- 速度图表
- WebSocket实时数据更新
- 最多显示100个数据点

#### Data Recorder (数据记录)
- 开始/停止录制控制
- 实验名称输入
- 录制状态指示
- 历史记录列表（待实现）

#### System Settings (系统设置)
- VIST参数显示
- 系统信息
- 关于页面

### 3. 启动脚本

**文件**:
- `web/start_web.sh` - 一键启动前后端
- `web/stop_web.sh` - 停止服务

**功能**:
- 自动检查依赖
- 自动安装缺失的包
- 后台启动服务
- PID管理
- 优雅关闭

## 项目结构

```
web/
├── backend/
│   ├── main.py              # FastAPI主服务器
│   └── requirements.txt     # Python依赖
├── frontend/
│   ├── src/
│   │   ├── pages/          # 页面组件
│   │   │   ├── Dashboard.tsx
│   │   │   ├── CameraManager.tsx
│   │   │   ├── PerformanceMonitor.tsx
│   │   │   ├── DataRecorder.tsx
│   │   │   └── SystemSettings.tsx
│   │   ├── App.tsx         # 主应用
│   │   ├── main.tsx        # 入口
│   │   └── index.css       # 全局样式
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── tailwind.config.js
├── start_web.sh            # 启动脚本
├── stop_web.sh             # 停止脚本
└── README.md               # 文档
```

## 使用方法

### 快速启动

```bash
cd /home/ilex/Dev/VIST
bash web/start_web.sh
```

然后在浏览器中打开: http://localhost:3000

### 手动启动

**后端**:
```bash
cd web/backend
pip install -r requirements.txt
python main.py
```

**前端**:
```bash
cd web/frontend
npm install
npm run dev
```

## 下一步开发计划

### 高优先级

1. **集成真实数据源**
   - 连接ROS2话题获取实时数据
   - 集成camera_manager
   - 集成performance_monitor
   - 集成data_logger

2. **3D机器人可视化**
   - 使用Three.js渲染机器人模型
   - 实时显示关节角度
   - 工作空间可视化

3. **相机实时预览**
   - WebRTC视频流
   - 多相机同时预览
   - 图像标注

### 中优先级

4. **轨迹回放**
   - 加载录制的轨迹数据
   - 可视化播放
   - 速度控制

5. **参数实时调整**
   - VIST参数滑块
   - 实时生效
   - 参数预设管理

6. **数据导出**
   - 导出为CSV/JSON
   - 性能报告生成
   - 图表导出

### 低优先级

7. **用户认证**
   - 登录系统
   - 权限管理

8. **多语言支持**
   - 中英文切换

9. **移动端适配**
   - 响应式设计优化

## 技术亮点

1. **实时通信**: WebSocket实现低延迟数据推送
2. **模块化设计**: 前后端分离，易于扩展
3. **类型安全**: TypeScript提供完整类型检查
4. **现代UI**: Tailwind CSS + 暗色主题
5. **性能优化**: Chart.js数据点限制，避免内存泄漏
6. **开发体验**: Vite热重载，FastAPI自动重载

## 集成建议

### 与ROS2集成

在后端API中添加ROS2订阅：

```python
import rclpy
from rclpy.node import Node

class ROS2Bridge(Node):
    def __init__(self):
        super().__init__('web_api_bridge')
        # 订阅性能监控话题
        self.create_subscription(
            PerformanceMetrics,
            '/performance/metrics',
            self.metrics_callback,
            10
        )

    def metrics_callback(self, msg):
        # 通过WebSocket推送到前端
        asyncio.create_task(
            manager.broadcast({
                'type': 'performance',
                'data': {
                    'tracking_error': msg.tracking_error,
                    'jerk': msg.jerk,
                    ...
                }
            })
        )
```

### 与camera_manager集成

```python
from src.camera_manager.camera_manager.multi_camera_manager import MultiCameraManager

@app.get("/api/cameras/list")
async def list_cameras():
    # 调用camera_manager获取相机列表
    cameras = camera_manager.get_cameras()
    return {"cameras": cameras}
```

## 故障排查

### 端口被占用

```bash
# 查找占用端口的进程
lsof -i :8000  # 后端
lsof -i :3000  # 前端

# 杀死进程
kill -9 <PID>
```

### 依赖安装失败

```bash
# 清除npm缓存
cd web/frontend
rm -rf node_modules package-lock.json
npm install

# 清除pip缓存
pip cache purge
pip install -r web/backend/requirements.txt
```

### WebSocket连接失败

1. 检查后端是否正常运行
2. 检查浏览器控制台错误
3. 确认防火墙设置

## 总结

VIST Web控制台提供了一个现代化的Web界面来监控和控制VIST遥操作系统。通过FastAPI后端和React前端的组合，实现了实时数据可视化、相机管理、性能监控等核心功能。

下一步需要将后端API与实际的VIST系统模块（ROS2、camera_manager、performance_monitor等）集成，实现真实数据的采集和展示。
