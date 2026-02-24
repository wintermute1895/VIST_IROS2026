import { useEffect, useState } from 'react'
import { Activity, Cpu, HardDrive, Wifi, TrendingUp } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

interface SystemStatus {
  vision_running: boolean
  robot_connected: boolean
  recording: boolean
  cpu_usage: number
  memory_usage: number
}

export default function Dashboard() {
  const [status, setStatus] = useState<SystemStatus | null>(null)

  useEffect(() => {
    console.log('🎨 Dashboard v2.0 with shadcn/ui loaded!')

    fetch('/api/system/status')
      .then(res => res.json())
      .then(data => setStatus(data))
      .catch(err => console.error('获取系统状态失败:', err))

    const interval = setInterval(() => {
      fetch('/api/system/status')
        .then(res => res.json())
        .then(data => setStatus(data))
        .catch(err => console.error('获取系统状态失败:', err))
    }, 1000)

    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-8">
      {/* 标题区域 */}
      <div className="mb-8">
        <h1 className="text-5xl font-bold bg-gradient-to-r from-blue-400 via-purple-500 to-pink-500 bg-clip-text text-transparent mb-3 animate-fade-in">
          系统监控
        </h1>
        <p className="text-gray-400 text-lg">实时监控VIST遥操作系统状态</p>
      </div>

      {/* 状态卡片网格 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <MetricCard
          icon={<Activity className="w-6 h-6" />}
          title="视觉系统"
          value={status?.vision_running ? '运行中' : '已停止'}
          status={status?.vision_running ? 'success' : 'error'}
          trend="+0%"
        />
        <MetricCard
          icon={<Wifi className="w-6 h-6" />}
          title="机器人连接"
          value={status?.robot_connected ? '已连接' : '未连接'}
          status={status?.robot_connected ? 'success' : 'error'}
          trend="稳定"
        />
        <MetricCard
          icon={<Cpu className="w-6 h-6" />}
          title="CPU使用率"
          value={`${status?.cpu_usage.toFixed(1) || 0}%`}
          status="info"
          trend="+2.5%"
        />
        <MetricCard
          icon={<HardDrive className="w-6 h-6" />}
          title="内存使用率"
          value={`${status?.memory_usage.toFixed(1) || 0}%`}
          status="info"
          trend="+1.2%"
        />
      </div>

      {/* 系统信息卡片 */}
      <Card>
        <CardHeader>
          <CardTitle>
            <div className="w-1 h-6 bg-gradient-to-b from-blue-500 to-purple-500 rounded-full mr-3"></div>
            系统信息
          </CardTitle>
          <CardDescription>VIST遥操作系统详细信息</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <InfoRow label="项目名称" value="VIST 遥操作系统" />
            <InfoRow label="版本" value="1.0.0" badge="最新" />
            <InfoRow label="运行时间" value="2小时34分钟" />
            <InfoRow label="数据目录" value="/home/ilex/Dev/VIST/data" />
            <InfoRow label="API状态" value="正常运行" badge="在线" />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

interface MetricCardProps {
  icon: React.ReactNode
  title: string
  value: string
  status: 'success' | 'error' | 'info'
  trend?: string
}

function MetricCard({ icon, title, value, status, trend }: MetricCardProps) {
  const statusConfig = {
    success: {
      gradient: 'from-green-500/20 to-green-600/10',
      border: 'border-green-500/30',
      text: 'text-green-400',
      glow: 'shadow-green-500/20',
      iconBg: 'bg-green-500/10'
    },
    error: {
      gradient: 'from-red-500/20 to-red-600/10',
      border: 'border-red-500/30',
      text: 'text-red-400',
      glow: 'shadow-red-500/20',
      iconBg: 'bg-red-500/10'
    },
    info: {
      gradient: 'from-blue-500/20 to-blue-600/10',
      border: 'border-blue-500/30',
      text: 'text-blue-400',
      glow: 'shadow-blue-500/20',
      iconBg: 'bg-blue-500/10'
    }
  }

  const config = statusConfig[status]

  return (
    <div className={`relative overflow-hidden rounded-2xl border p-6 bg-gradient-to-br ${config.gradient} ${config.border} backdrop-blur-sm shadow-xl ${config.glow} hover:scale-105 transition-all duration-300 group`}>
      {/* 背景装饰 */}
      <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-white/5 to-transparent rounded-full blur-2xl group-hover:scale-150 transition-transform duration-500"></div>

      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className={`p-3 rounded-xl ${config.iconBg} backdrop-blur-sm ${config.text}`}>
            {icon}
          </div>
          <div className="text-right">
            <div className={`text-3xl font-bold ${config.text}`}>{value}</div>
            {trend && (
              <div className="flex items-center justify-end text-xs text-gray-400 mt-1">
                <TrendingUp className="w-3 h-3 mr-1" />
                {trend}
              </div>
            )}
          </div>
        </div>
        <p className="text-sm opacity-80 font-medium text-gray-300">{title}</p>
      </div>
    </div>
  )
}

interface InfoRowProps {
  label: string
  value: string
  badge?: string
}

function InfoRow({ label, value, badge }: InfoRowProps) {
  return (
    <div className="flex justify-between items-center py-3 border-b border-gray-700/50 hover:border-blue-500/30 transition-colors duration-200 group">
      <span className="text-gray-400 group-hover:text-gray-300 transition-colors font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-medium text-gray-200 group-hover:text-white transition-colors">{value}</span>
        {badge && (
          <span className="px-2 py-1 text-xs font-semibold rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
            {badge}
          </span>
        )}
      </div>
    </div>
  )
}
