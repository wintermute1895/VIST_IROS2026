#!/usr/bin/env python3
"""
VIST 双臂数据流 Web 可视化工具
实时显示数据流、频率、方向修正等信息
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import numpy as np
from collections import deque
import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import time

class DataFlowWebVisualizer(Node):
    def __init__(self):
        super().__init__('data_flow_web_visualizer')

        # 数据存储
        self.data = {
            'linkerta_left': {'values': deque(maxlen=100), 'freq': 0, 'last_time': 0},
            'linkerta_right': {'values': deque(maxlen=100), 'freq': 0, 'last_time': 0},
            'filtered_left': {'values': deque(maxlen=100), 'freq': 0, 'last_time': 0},
            'filtered_right': {'values': deque(maxlen=100), 'freq': 0, 'last_time': 0},
            'bridge_left': {'values': deque(maxlen=100), 'freq': 0, 'last_time': 0},
            'bridge_right': {'values': deque(maxlen=100), 'freq': 0, 'last_time': 0},
        }

        # 配置
        self.left_directions = [1, 1, -1, 1, -1, 1, 1]
        self.right_directions = [-1, 1, -1, 1, -1, -1, 1]

        # 订阅所有话题
        self.create_subscription(JointState, '/left_arm_joint_control',
                                lambda msg: self.update_data('linkerta_left', msg), 10)
        self.create_subscription(JointState, '/right_arm_joint_control',
                                lambda msg: self.update_data('linkerta_right', msg), 10)
        self.create_subscription(JointState, '/filtered_left_joint_control',
                                lambda msg: self.update_data('filtered_left', msg), 10)
        self.create_subscription(JointState, '/filtered_right_joint_control',
                                lambda msg: self.update_data('filtered_right', msg), 10)

        # 尝试订阅桥接节点话题（可能不存在）
        try:
            from lbot_arm_interfaces.msg import FollowJoint
            self.create_subscription(FollowJoint, '/robot1/left_arm/joint_follow',
                                    lambda msg: self.update_bridge_data('bridge_left', msg), 10)
            self.create_subscription(FollowJoint, '/robot1/right_arm/joint_follow',
                                    lambda msg: self.update_bridge_data('bridge_right', msg), 10)
        except:
            self.get_logger().warn('无法订阅桥接节点话题（可能未启动）')

        # 定时更新频率
        self.create_timer(0.1, self.update_frequencies)

        print('Web可视化工具已启动')
        print('访问: http://localhost:8000')

    def update_data(self, key, msg):
        """更新数据"""
        current_time = time.time()
        self.data[key]['values'].append(list(msg.position[:7]))
        self.data[key]['last_time'] = current_time

    def update_bridge_data(self, key, msg):
        """更新桥接节点数据"""
        current_time = time.time()
        self.data[key]['values'].append(list(msg.joints[:7]))
        self.data[key]['last_time'] = current_time

    def update_frequencies(self):
        """更新频率统计"""
        current_time = time.time()
        for key, data in self.data.items():
            if len(data['values']) > 1:
                # 简单频率估算
                time_diff = current_time - data['last_time']
                if time_diff < 1.0:  # 1秒内有数据
                    data['freq'] = len(data['values']) / 10.0  # 粗略估算
                else:
                    data['freq'] = 0

    def get_status(self):
        """获取当前状态（用于Web API）"""
        status = {}
        for key, data in self.data.items():
            latest = list(data['values'][-1]) if len(data['values']) > 0 else [0]*7
            status[key] = {
                'latest': latest,
                'freq': data['freq'],
                'count': len(data['values'])
            }

        # 验证方向修正
        if len(self.data['linkerta_left']['values']) > 0 and len(self.data['filtered_left']['values']) > 0:
            raw = np.array(self.data['linkerta_left']['values'][-1])
            filtered = np.array(self.data['filtered_left']['values'][-1])
            expected = raw * np.array(self.left_directions)
            status['left_direction_ok'] = np.allclose(filtered, expected, atol=0.01)
        else:
            status['left_direction_ok'] = None

        if len(self.data['linkerta_right']['values']) > 0 and len(self.data['filtered_right']['values']) > 0:
            raw = np.array(self.data['linkerta_right']['values'][-1])
            filtered = np.array(self.data['filtered_right']['values'][-1])
            expected = raw * np.array(self.right_directions)
            status['right_direction_ok'] = np.allclose(filtered, expected, atol=0.01)
        else:
            status['right_direction_ok'] = None

        return status

# 全局变量
visualizer = None

class APIHandler(SimpleHTTPRequestHandler):
    """HTTP请求处理器"""

    def do_GET(self):
        if self.path == '/api/status':
            # 返回JSON状态
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            if visualizer:
                status = visualizer.get_status()
                self.wfile.write(json.dumps(status).encode())
            else:
                self.wfile.write(b'{}')

        elif self.path == '/' or self.path == '/index.html':
            # 返回HTML页面
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())

        else:
            self.send_error(404)

    def log_message(self, format, *args):
        # 禁用日志输出
        pass

HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>VIST 双臂数据流可视化</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: #4ec9b0;
            text-align: center;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: #252526;
            border: 1px solid #3e3e42;
            border-radius: 8px;
            padding: 20px;
        }
        .card h2 {
            color: #569cd6;
            margin-top: 0;
            font-size: 18px;
        }
        .status {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 10px 0;
            padding: 10px;
            background: #2d2d30;
            border-radius: 4px;
        }
        .status-ok {
            border-left: 4px solid #4ec9b0;
        }
        .status-error {
            border-left: 4px solid #f48771;
        }
        .status-inactive {
            border-left: 4px solid #858585;
        }
        .freq {
            color: #4ec9b0;
            font-weight: bold;
        }
        .joint-values {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 5px;
            margin-top: 10px;
        }
        .joint-value {
            background: #2d2d30;
            padding: 8px;
            text-align: center;
            border-radius: 4px;
            font-size: 12px;
        }
        .joint-label {
            color: #858585;
            font-size: 10px;
        }
        .verification {
            margin-top: 20px;
            padding: 15px;
            background: #2d2d30;
            border-radius: 4px;
        }
        .verification-ok {
            border-left: 4px solid #4ec9b0;
        }
        .verification-error {
            border-left: 4px solid #f48771;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 VIST 双臂数据流实时监控</h1>

        <div class="grid">
            <!-- 左臂数据流 -->
            <div class="card">
                <h2>🦾 左臂数据流</h2>
                <div id="left-linkerta" class="status status-inactive">
                    <span>LinkerTA 原始数据</span>
                    <span class="freq">-- Hz</span>
                </div>
                <div class="joint-values" id="left-linkerta-values"></div>

                <div id="left-filtered" class="status status-inactive">
                    <span>滤波后数据</span>
                    <span class="freq">-- Hz</span>
                </div>
                <div class="joint-values" id="left-filtered-values"></div>

                <div id="left-bridge" class="status status-inactive">
                    <span>桥接节点输出</span>
                    <span class="freq">-- Hz</span>
                </div>
                <div class="joint-values" id="left-bridge-values"></div>

                <div id="left-verification" class="verification">
                    <strong>方向修正验证:</strong> <span id="left-verify-status">等待数据...</span>
                </div>
            </div>

            <!-- 右臂数据流 -->
            <div class="card">
                <h2>🦾 右臂数据流</h2>
                <div id="right-linkerta" class="status status-inactive">
                    <span>LinkerTA 原始数据</span>
                    <span class="freq">-- Hz</span>
                </div>
                <div class="joint-values" id="right-linkerta-values"></div>

                <div id="right-filtered" class="status status-inactive">
                    <span>滤波后数据</span>
                    <span class="freq">-- Hz</span>
                </div>
                <div class="joint-values" id="right-filtered-values"></div>

                <div id="right-bridge" class="status status-inactive">
                    <span>桥接节点输出</span>
                    <span class="freq">-- Hz</span>
                </div>
                <div class="joint-values" id="right-bridge-values"></div>

                <div id="right-verification" class="verification">
                    <strong>方向修正验证:</strong> <span id="right-verify-status">等待数据...</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        function updateStatus() {
            fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    // 更新左臂
                    updateTopic('left-linkerta', data.linkerta_left);
                    updateTopic('left-filtered', data.filtered_left);
                    updateTopic('left-bridge', data.bridge_left);

                    // 更新右臂
                    updateTopic('right-linkerta', data.linkerta_right);
                    updateTopic('right-filtered', data.filtered_right);
                    updateTopic('right-bridge', data.bridge_right);

                    // 更新验证状态
                    updateVerification('left', data.left_direction_ok);
                    updateVerification('right', data.right_direction_ok);
                })
                .catch(err => console.error('Error:', err));
        }

        function updateTopic(id, data) {
            const elem = document.getElementById(id);
            const valuesElem = document.getElementById(id + '-values');

            if (data && data.count > 0) {
                elem.className = 'status status-ok';
                elem.querySelector('.freq').textContent = data.freq.toFixed(1) + ' Hz';

                // 更新关节值
                valuesElem.innerHTML = data.latest.map((val, i) =>
                    `<div class="joint-value">
                        <div class="joint-label">J${i}</div>
                        <div>${val.toFixed(2)}</div>
                    </div>`
                ).join('');
            } else {
                elem.className = 'status status-inactive';
                elem.querySelector('.freq').textContent = '-- Hz';
                valuesElem.innerHTML = '';
            }
        }

        function updateVerification(arm, status) {
            const elem = document.getElementById(arm + '-verification');
            const statusElem = document.getElementById(arm + '-verify-status');

            if (status === null) {
                elem.className = 'verification';
                statusElem.textContent = '等待数据...';
            } else if (status) {
                elem.className = 'verification verification-ok';
                statusElem.textContent = '✓ 方向修正正确';
            } else {
                elem.className = 'verification verification-error';
                statusElem.textContent = '✗ 方向修正异常';
            }
        }

        // 每100ms更新一次
        setInterval(updateStatus, 100);
        updateStatus();
    </script>
</body>
</html>
"""

def start_web_server():
    """启动Web服务器"""
    server = HTTPServer(('localhost', 8000), APIHandler)
    print('Web服务器启动在 http://localhost:8000')
    server.serve_forever()

def main():
    global visualizer

    rclpy.init()
    visualizer = DataFlowWebVisualizer()

    # 在单独的线程中启动Web服务器
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    print('')
    print('=' * 60)
    print('VIST 双臂数据流 Web 可视化工具')
    print('=' * 60)
    print('')
    print('访问: http://localhost:8000')
    print('')
    print('功能:')
    print('  - 实时显示所有话题的数据')
    print('  - 监控数据频率')
    print('  - 验证方向修正')
    print('  - 显示关节值')
    print('')
    print('按 Ctrl+C 停止')
    print('=' * 60)
    print('')

    try:
        rclpy.spin(visualizer)
    except KeyboardInterrupt:
        print('\n\n可视化工具已停止')
    finally:
        visualizer.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()