import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import { Activity, Camera, Database, Settings, BarChart3 } from 'lucide-react'
import Dashboard from './pages/Dashboard'
import CameraManager from './pages/CameraManager'
import PerformanceMonitor from './pages/PerformanceMonitor'
import DataRecorder from './pages/DataRecorder'
import SystemSettings from './pages/SystemSettings'

function App() {
  return (
    <Router>
      <div className="flex h-screen bg-gray-900 text-white">
        {/* 侧边栏 */}
        <aside className="w-64 bg-gray-800 border-r border-gray-700">
          <div className="p-6">
            <h1 className="text-2xl font-bold text-primary-400">VIST 系统</h1>
            <p className="text-sm text-gray-400 mt-1">遥操作控制台</p>
          </div>

          <nav className="mt-6">
            <NavLink to="/" icon={<Activity />} label="系统监控" />
            <NavLink to="/cameras" icon={<Camera />} label="相机管理" />
            <NavLink to="/performance" icon={<BarChart3 />} label="性能监控" />
            <NavLink to="/recorder" icon={<Database />} label="数据记录" />
            <NavLink to="/settings" icon={<Settings />} label="系统设置" />
          </nav>

          <div className="absolute bottom-0 left-0 right-0 p-6 border-t border-gray-700">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
              <span className="text-sm text-gray-400">系统运行中</span>
            </div>
          </div>
        </aside>

        {/* 主内容区 */}
        <main className="flex-1 overflow-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cameras" element={<CameraManager />} />
            <Route path="/performance" element={<PerformanceMonitor />} />
            <Route path="/recorder" element={<DataRecorder />} />
            <Route path="/settings" element={<SystemSettings />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

interface NavLinkProps {
  to: string
  icon: React.ReactNode
  label: string
}

function NavLink({ to, icon, label }: NavLinkProps) {
  return (
    <Link
      to={to}
      className="flex items-center space-x-3 px-6 py-3 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
    >
      <span className="w-5 h-5">{icon}</span>
      <span>{label}</span>
    </Link>
  )
}

export default App
