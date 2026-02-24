#!/usr/bin/env python3
"""
VIST Web API 服务器
提供RESTful API和WebSocket实时数据推送

功能：
1. 系统状态监控
2. 相机管理
3. 性能数据推送
4. 数据采集控制
5. 参数配置

Author: VIST Project
Date: 2026-02-23
"""

import os
import sys
import asyncio
import json
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

# 导入VIST模块（延迟初始化，避免占用相机）
camera_manager = None
system_monitor = None

def get_camera_manager_instance():
    """延迟初始化相机管理器"""
    global camera_manager
    if camera_manager is None:
        try:
            from src.perception.realsense_manager import get_manager as get_camera_manager
            camera_manager = get_camera_manager()
        except Exception as e:
            print(f"⚠️ 无法导入相机管理器: {e}")
    return camera_manager

def get_system_monitor_instance():
    """延迟初始化系统监控器"""
    global system_monitor
    if system_monitor is None:
        try:
            from src.monitoring.system_monitor import get_monitor as get_system_monitor
            system_monitor = get_system_monitor()
        except Exception as e:
            print(f"⚠️ 无法导入系统监控器: {e}")
    return system_monitor

# 创建FastAPI应用
app = FastAPI(
    title="VIST Web API",
    description="VIST遥操作系统Web API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket连接管理
class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ WebSocket连接: {len(self.active_connections)} 个活跃连接")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"❌ WebSocket断开: {len(self.active_connections)} 个活跃连接")

    async def broadcast(self, message: dict):
        """广播消息到所有连接"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"⚠️ 发送消息失败: {e}")

manager = ConnectionManager()

# ==========================================
# 数据模型
# ==========================================

class SystemStatus(BaseModel):
    """系统状态"""
    timestamp: float
    vision_running: bool
    robot_connected: bool
    recording: bool
    cpu_usage: float
    memory_usage: float

class CameraInfo(BaseModel):
    """相机信息"""
    serial_number: str
    name: str
    model: str
    status: str
    resolution: str
    fps: int

class PerformanceMetrics(BaseModel):
    """性能指标"""
    timestamp: float
    tracking_error: float
    jerk: float
    velocity: float
    acceleration: float
    packet_loss: float

# ==========================================
# API路由
# ==========================================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "VIST Web API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/api/system/status")
async def get_system_status():
    """获取系统状态"""
    try:
        monitor = get_system_monitor_instance()
        if monitor is None:
            # 降级到基础监控
            import psutil
            return {
                "timestamp": datetime.now().timestamp(),
                "vision_running": False,
                "robot_connected": False,
                "recording": False,
                "cpu_usage": psutil.cpu_percent(interval=0.1),
                "memory_usage": psutil.virtual_memory().percent
            }

        # 使用系统监控器获取真实状态
        status = monitor.get_system_status()
        return status

    except Exception as e:
        print(f"❌ 获取系统状态失败: {e}")
        return {
            "timestamp": datetime.now().timestamp(),
            "vision_running": False,
            "robot_connected": False,
            "recording": False,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "error": str(e)
        }

@app.get("/api/cameras/list")
async def list_cameras():
    """列出所有相机"""
    try:
        manager = get_camera_manager_instance()
        if manager is None:
            return {
                "cameras": [],
                "error": "相机管理器未初始化"
            }

        # 检测相机
        cameras = manager.detect_cameras()

        # 转换为API格式
        camera_list = []
        for cam in cameras:
            serial_number = cam['serial_number']
            # 检查相机是否正在运行
            is_running = serial_number in manager.pipelines

            camera_list.append({
                "serial_number": serial_number,
                "name": cam['name'],
                "model": cam['name'].split()[0] if cam['name'] else "Unknown",
                "status": "running" if is_running else "connected",
                "firmware_version": cam['firmware_version'],
                "usb_type": cam['usb_type'],
                "resolution": "640x480",  # 默认分辨率
                "fps": 30
            })

        return {
            "cameras": camera_list,
            "count": len(camera_list)
        }

    except Exception as e:
        print(f"❌ 获取相机列表失败: {e}")
        return {
            "cameras": [],
            "error": str(e)
        }

@app.post("/api/cameras/{serial_number}/start")
async def start_camera(serial_number: str, width: int = 640, height: int = 480, fps: int = 30):
    """启动指定相机"""
    try:
        manager = get_camera_manager_instance()
        if manager is None:
            return {
                "status": "error",
                "message": "相机管理器未初始化"
            }

        # 启动相机
        success = manager.start_camera(serial_number, width, height, fps)

        if success:
            return {
                "status": "success",
                "message": f"相机 {serial_number} 启动成功"
            }
        else:
            return {
                "status": "error",
                "message": f"相机 {serial_number} 启动失败"
            }

    except Exception as e:
        print(f"❌ 启动相机失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/api/cameras/{serial_number}/stop")
async def stop_camera(serial_number: str):
    """停止指定相机"""
    try:
        manager = get_camera_manager_instance()
        if manager is None:
            return {
                "status": "error",
                "message": "相机管理器未初始化"
            }

        # 停止相机
        success = manager.stop_camera(serial_number)

        if success:
            return {
                "status": "success",
                "message": f"相机 {serial_number} 已停止"
            }
        else:
            return {
                "status": "error",
                "message": f"相机 {serial_number} 停止失败或未运行"
            }

    except Exception as e:
        print(f"❌ 停止相机失败: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/api/performance/metrics")
async def get_performance_metrics():
    """获取性能指标"""
    # TODO: 从performance_monitor获取数据
    return {
        "timestamp": datetime.now().timestamp(),
        "tracking_error": 0.0,
        "jerk": 0.0,
        "velocity": 0.0,
        "acceleration": 0.0,
        "packet_loss": 0.0
    }

@app.post("/api/recording/start")
async def start_recording(experiment_name: Optional[str] = None):
    """开始数据记录"""
    # TODO: 启动数据记录
    return {
        "status": "success",
        "experiment_name": experiment_name or f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    }

@app.post("/api/recording/stop")
async def stop_recording():
    """停止数据记录"""
    # TODO: 停止数据记录
    return {"status": "success"}

@app.get("/api/recordings/list")
async def list_recordings():
    """列出所有录制数据"""
    data_dir = Path(project_root) / "data" / "experiments"
    if not data_dir.exists():
        return {"recordings": []}

    recordings = []
    for exp_dir in data_dir.iterdir():
        if exp_dir.is_dir():
            recordings.append({
                "name": exp_dir.name,
                "path": str(exp_dir),
                "created": exp_dir.stat().st_ctime
            })

    return {"recordings": recordings}

@app.get("/api/config")
async def get_config():
    """获取系统配置"""
    # TODO: 从config模块获取配置
    return {
        "vist_enabled": True,
        "control_frequency": 60,
        "ik_strategy": "vist"
    }

@app.post("/api/config")
async def update_config(config: dict):
    """更新系统配置"""
    # TODO: 更新配置
    return {"status": "success", "config": config}

# ==========================================
# WebSocket路由
# ==========================================

@app.websocket("/ws/realtime")
async def websocket_realtime(websocket: WebSocket):
    """实时数据推送WebSocket"""
    await manager.connect(websocket)

    try:
        while True:
            # 接收客户端消息（心跳）
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

            # 推送实时数据
            realtime_data = {
                "type": "performance",
                "timestamp": datetime.now().timestamp(),
                "data": {
                    "tracking_error": 0.0,
                    "jerk": 0.0,
                    "velocity": 0.0,
                    "fps": 30.0
                }
            }
            await websocket.send_json(realtime_data)

            await asyncio.sleep(0.1)  # 10Hz推送频率

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"⚠️ WebSocket错误: {e}")
        manager.disconnect(websocket)

# ==========================================
# 后台任务
# ==========================================

@app.on_event("startup")
async def startup_event():
    """启动时执行"""
    print("=" * 80)
    print("🚀 VIST Web API 服务器启动")
    print("=" * 80)
    print(f"   项目根目录: {project_root}")
    print(f"   API文档: http://localhost:8000/docs")
    print("=" * 80)

@app.on_event("shutdown")
async def shutdown_event():
    """关闭时执行"""
    print("\n🛑 VIST Web API 服务器关闭")

# ==========================================
# 主函数
# ==========================================

def main():
    """启动服务器"""
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式自动重载
        log_level="info"
    )

if __name__ == "__main__":
    main()
