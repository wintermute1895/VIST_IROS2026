import { useEffect, useState, useRef } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
)

interface PerformanceData {
  timestamp: number
  tracking_error: number
  jerk: number
  velocity: number
  acceleration: number
  packet_loss: number
}

const MAX_DATA_POINTS = 100

export default function PerformanceMonitor() {
  const [data, setData] = useState<PerformanceData[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // 建立WebSocket连接
    const ws = new WebSocket('ws://localhost:8000/ws/realtime')
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket连接已建立')
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      if (message.type === 'performance') {
        setData((prev) => {
          const newData = [...prev, message.data]
          return newData.slice(-MAX_DATA_POINTS)
        })
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket错误:', error)
    }

    ws.onclose = () => {
      console.log('WebSocket连接已关闭')
    }

    return () => {
      ws.close()
    }
  }, [])

  const chartOptions: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          color: '#9CA3AF',
        },
      },
    },
    scales: {
      x: {
        ticks: { color: '#9CA3AF' },
        grid: { color: '#374151' },
      },
      y: {
        ticks: { color: '#9CA3AF' },
        grid: { color: '#374151' },
      },
    },
  }

  const trackingErrorData = {
    labels: data.map((_, i) => i.toString()),
    datasets: [
      {
        label: '追踪误差 (mm)',
        data: data.map((d) => d.tracking_error * 1000),
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
      },
    ],
  }

  const jerkData = {
    labels: data.map((_, i) => i.toString()),
    datasets: [
      {
        label: 'Jerk (m/s³)',
        data: data.map((d) => d.jerk),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        tension: 0.4,
      },
    ],
  }

  const velocityData = {
    labels: data.map((_, i) => i.toString()),
    datasets: [
      {
        label: '速度 (m/s)',
        data: data.map((d) => d.velocity),
        borderColor: 'rgb(34, 197, 94)',
        backgroundColor: 'rgba(34, 197, 94, 0.1)',
        tension: 0.4,
      },
    ],
  }

  const currentMetrics = data[data.length - 1] || {
    tracking_error: 0,
    jerk: 0,
    velocity: 0,
    acceleration: 0,
    packet_loss: 0,
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">性能监控</h1>

      {/* 实时指标卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
        <MetricCard
          label="追踪误差"
          value={`${(currentMetrics.tracking_error * 1000).toFixed(2)} mm`}
          color="blue"
        />
        <MetricCard
          label="Jerk"
          value={`${currentMetrics.jerk.toFixed(3)} m/s³`}
          color="red"
        />
        <MetricCard
          label="速度"
          value={`${currentMetrics.velocity.toFixed(3)} m/s`}
          color="green"
        />
        <MetricCard
          label="加速度"
          value={`${currentMetrics.acceleration.toFixed(3)} m/s²`}
          color="yellow"
        />
        <MetricCard
          label="丢包率"
          value={`${(currentMetrics.packet_loss * 100).toFixed(1)}%`}
          color="purple"
        />
      </div>

      {/* 图表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ChartCard title="追踪误差">
          <Line options={chartOptions} data={trackingErrorData} />
        </ChartCard>
        <ChartCard title="Jerk (平滑度指标)">
          <Line options={chartOptions} data={jerkData} />
        </ChartCard>
        <ChartCard title="速度">
          <Line options={chartOptions} data={velocityData} />
        </ChartCard>
        <ChartCard title="系统状态">
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-6xl font-bold text-green-500 mb-2">
                {data.length > 0 ? '30' : '0'}
              </div>
              <div className="text-gray-400">FPS</div>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: string
  color: 'blue' | 'red' | 'green' | 'yellow' | 'purple'
}

function MetricCard({ label, value, color }: MetricCardProps) {
  const colorClasses = {
    blue: 'bg-blue-500/10 border-blue-500/20 text-blue-500',
    red: 'bg-red-500/10 border-red-500/20 text-red-500',
    green: 'bg-green-500/10 border-green-500/20 text-green-500',
    yellow: 'bg-yellow-500/10 border-yellow-500/20 text-yellow-500',
    purple: 'bg-purple-500/10 border-purple-500/20 text-purple-500',
  }

  return (
    <div className={`rounded-lg border p-4 ${colorClasses[color]}`}>
      <div className="text-sm opacity-80 mb-1">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  )
}

interface ChartCardProps {
  title: string
  children: React.ReactNode
}

function ChartCard({ title, children }: ChartCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="h-64">{children}</div>
    </div>
  )
}
