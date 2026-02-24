# VIST Web 控制台

VIST遥操作系统的Web控制台，提供实时监控、相机管理、性能分析等功能。

## 功能模块

### 1. 系统监控 (Dashboard)
- 实时系统状态
- CPU/内存使用率
- 视觉系统状态
- 机器人连接状态

### 2. 相机管理 (Camera Manager)
- 列出所有连接的RealSense相机
- 启动/停止相机
- 查看相机参数
- 实时预览（开发中）

### 3. 性能监控 (Performance Monitor)
- 实时性能图表
- 追踪误差
- Jerk（平滑度指标）
- 速度和加速度
- 丢包率

### 4. 数据记录 (Data Recorder)
- 开始/停止数据录制
- 查看历史记录
- 播放轨迹（开发中）

### 5. 系统设置 (System Settings)
- VIST参数配置
- 系统信息

## 技术栈

### 前端
- React 18
- TypeScript
- Vite
- Tailwind CSS
- Chart.js (图表)
- Three.js (3D可视化，开发中)
- React Router (路由)

### 后端
- FastAPI
- WebSocket (实时数据推送)
- Python 3.10+

## 安装和运行

### 1. 安装后端依赖

```bash
cd web/backend
pip install -r requirements.txt
```

### 2. 安装前端依赖

```bash
cd web/frontend
npm install
```

### 3. 启动后端服务器

```bash
cd web/backend
python main.py
```

后端API将运行在 http://localhost:8000
API文档: http://localhost:8000/docs

### 4. 启动前端开发服务器

```bash
cd web/frontend
npm run dev
```

前端将运行在 http://localhost:3000

## 快速启动脚本

使用提供的启动脚本一键启动前后端：

```bash
cd /home/ilex/Dev/VIST
bash web/start_web.sh
```

## 开发

### 前端开发

```bash
cd web/frontend
npm run dev      # 开发模式
npm run build    # 生产构建
npm run preview  # 预览生产构建
```

### 后端开发

后端使用FastAPI的自动重载功能，修改代码后会自动重启。

## 项目结构

```
web/
├── frontend/              # React前端
│   ├── src/
│   │   ├── components/   # 可复用组件
│   │   ├── pages/        # 页面组件
│   │   ├── hooks/        # 自定义Hooks
│   │   ├── utils/        # 工具函数
│   │   ├── types/        # TypeScript类型
│   │   ├── App.tsx       # 主应用组件
│   │   └── main.tsx      # 入口文件
│   ├── package.json
│   └── vite.config.ts
├── backend/              # FastAPI后端
│   ├── main.py          # 主服务器
│   ├── api/             # API路由
│   └── requirements.txt
└── README.md
```

## API端点

### REST API

- `GET /api/system/status` - 获取系统状态
- `GET /api/cameras/list` - 列出所有相机
- `POST /api/cameras/{name}/start` - 启动相机
- `POST /api/cameras/{name}/stop` - 停止相机
- `GET /api/performance/metrics` - 获取性能指标
- `POST /api/recording/start` - 开始录制
- `POST /api/recording/stop` - 停止录制
- `GET /api/recordings/list` - 列出录制数据
- `GET /api/config` - 获取配置
- `POST /api/config` - 更新配置

### WebSocket

- `ws://localhost:8000/ws/realtime` - 实时数据推送

## 待开发功能

- [ ] 3D机器人可视化
- [ ] 相机实时预览
- [ ] 轨迹回放
- [ ] 参数实时调整
- [ ] 用户认证
- [ ] 数据导出
- [ ] 多语言支持

## 故障排查

### 前端无法连接后端

1. 确认后端服务器正在运行
2. 检查端口8000是否被占用
3. 查看浏览器控制台错误信息

### WebSocket连接失败

1. 确认后端WebSocket端点正常
2. 检查防火墙设置
3. 查看后端日志

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License
