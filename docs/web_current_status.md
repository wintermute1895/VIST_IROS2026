# VIST Web控制台 - 当前状态

## ✅ 已完成

### 后端API服务器
- **状态**: ✅ 正常运行
- **地址**: http://localhost:8000
- **API文档**: http://localhost:8000/docs

**测试结果**:
```bash
$ curl http://localhost:8000/
{"name":"VIST Web API","version":"1.0.0","status":"running"}

$ curl http://localhost:8000/api/system/status
{
    "timestamp": 1771859491.005115,
    "vision_running": false,
    "robot_connected": false,
    "recording": false,
    "cpu_usage": 0.0,
    "memory_usage": 0.0
}

$ curl http://localhost:8000/api/cameras/list
{
    "cameras": [
        {
            "serial_number": "123456789",
            "name": "mediapipe_camera",
            "model": "D435i",
            "status": "connected",
            "resolution": "640x480",
            "fps": 30
        }
    ]
}
```

### 可用的API端点

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/` | 服务器状态 |
| GET | `/api/system/status` | 系统状态 |
| GET | `/api/cameras/list` | 相机列表 |
| POST | `/api/cameras/{name}/start` | 启动相机 |
| POST | `/api/cameras/{name}/stop` | 停止相机 |
| GET | `/api/performance/metrics` | 性能指标 |
| POST | `/api/recording/start` | 开始录制 |
| POST | `/api/recording/stop` | 停止录制 |
| GET | `/api/recordings/list` | 录制列表 |
| GET | `/api/config` | 获取配置 |
| POST | `/api/config` | 更新配置 |
| WS | `/ws/realtime` | 实时数据推送 |

## ⚠️ 待解决

### 前端Web应用
- **状态**: ❌ 无法启动
- **原因**: Node.js版本过旧（v12.22.9），缺少npm
- **需要**: Node.js 16+ 和 npm

## 🚀 使用方法

### 当前可用：后端API

```bash
# 启动后端
cd /home/ilex/Dev/VIST
bash web/start_backend_only.sh

# 访问API文档
# 在浏览器中打开: http://localhost:8000/docs
```

### 测试API

```bash
# 获取系统状态
curl http://localhost:8000/api/system/status

# 获取相机列表
curl http://localhost:8000/api/cameras/list

# 获取性能指标
curl http://localhost:8000/api/performance/metrics
```

### 使用Postman/Insomnia测试

1. 打开Postman或Insomnia
2. 导入API端点
3. 测试各个功能

## 📋 下一步

### 选项1：安装Node.js（推荐）

安装Node.js 18后可以使用完整的Web界面：

```bash
# 使用NodeSource安装
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# 验证
node --version  # 应该是 v18.x.x
npm --version   # 应该是 9.x.x

# 启动完整Web控制台
bash web/start_web.sh
```

详细安装指南: [docs/nodejs_installation_guide.md](nodejs_installation_guide.md)

### 选项2：继续使用后端API

如果暂时不需要Web界面，可以：
1. 使用API文档测试功能
2. 使用curl/Postman调用API
3. 编写Python脚本调用API

### 选项3：集成到现有系统

将后端API集成到VIST系统：

```python
# 在VIST代码中调用API
import requests

# 获取系统状态
response = requests.get('http://localhost:8000/api/system/status')
status = response.json()

# 启动相机
requests.post('http://localhost:8000/api/cameras/mediapipe_camera/start')
```

## 🔧 集成计划

### 短期（1-2天）

1. **安装Node.js** - 启用完整Web界面
2. **集成ROS2数据** - 连接实际的相机和性能监控
3. **测试WebSocket** - 验证实时数据推送

### 中期（1周）

4. **3D可视化** - 添加机器人模型显示
5. **相机预览** - 实时视频流
6. **数据回放** - 轨迹播放功能

### 长期（2-4周）

7. **参数调整** - 实时修改VIST参数
8. **数据分析** - 性能报告生成
9. **移动端** - 响应式设计优化

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    VIST系统                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 视觉系统      │  │ 相机管理      │  │ 性能监控      │ │
│  │              │  │              │  │              │ │
│  │ vision_node  │  │ camera_mgr   │  │ perf_monitor │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
│         │                 │                 │          │
│         └─────────────────┼─────────────────┘          │
│                           │                            │
└───────────────────────────┼────────────────────────────┘
                            │
                     ┌──────▼───────┐
                     │  Web API     │ ✅ 运行中
                     │  (FastAPI)   │
                     └──────┬───────┘
                            │
                     ┌──────▼───────┐
                     │  Web前端     │ ❌ 需要Node.js
                     │  (React)     │
                     └──────────────┘
```

## 📝 文档

- [Web控制台README](../web/README.md)
- [实现总结](web_frontend_implementation.md)
- [Node.js安装指南](nodejs_installation_guide.md)
- [架构分析](architecture_analysis.md)

## 🎯 总结

**当前状态**: 后端API已成功部署并运行，可以通过HTTP请求访问所有功能。

**下一步**: 安装Node.js 18以启用完整的Web界面，或继续使用API进行开发和测试。

**推荐**: 先使用API文档（http://localhost:8000/docs）熟悉功能，然后安装Node.js体验完整界面。
