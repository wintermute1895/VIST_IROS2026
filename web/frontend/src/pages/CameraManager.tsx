import { useEffect, useState } from 'react'
import { Camera, Play, Square, RefreshCw } from 'lucide-react'

interface CameraInfo {
  serial_number: string
  name: string
  model: string
  status: string
  resolution: string
  fps: number
}

export default function CameraManager() {
  const [cameras, setCameras] = useState<CameraInfo[]>([])
  const [loading, setLoading] = useState(false)

  const loadCameras = async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/cameras/list')
      const data = await res.json()
      setCameras(data.cameras || [])
    } catch (err) {
      console.error('加载相机列表失败:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCameras()
  }, [])

  const handleStartCamera = async (serialNumber: string) => {
    try {
      const res = await fetch(`/api/cameras/${serialNumber}/start`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'success') {
        console.log('✅ 相机启动成功:', data.message)
      } else {
        console.error('❌ 相机启动失败:', data.message)
        alert(`启动失败: ${data.message}`)
      }
      // 延迟刷新，给相机时间启动
      setTimeout(loadCameras, 1000)
    } catch (err) {
      console.error('启动相机失败:', err)
      alert('启动相机失败，请查看控制台')
    }
  }

  const handleStopCamera = async (serialNumber: string) => {
    try {
      const res = await fetch(`/api/cameras/${serialNumber}/stop`, { method: 'POST' })
      const data = await res.json()
      if (data.status === 'success') {
        console.log('✅ 相机停止成功:', data.message)
      } else {
        console.error('❌ 相机停止失败:', data.message)
        alert(`停止失败: ${data.message}`)
      }
      loadCameras()
    } catch (err) {
      console.error('停止相机失败:', err)
      alert('停止相机失败，请查看控制台')
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-3xl font-bold">相机管理</h1>
        <button
          onClick={loadCameras}
          disabled={loading}
          className="flex items-center space-x-2 px-4 py-2 bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          <span>刷新</span>
        </button>
      </div>

      {cameras.length === 0 ? (
        <div className="bg-gray-800 rounded-lg p-12 text-center">
          <Camera className="w-16 h-16 mx-auto mb-4 text-gray-600" />
          <p className="text-gray-400">未检测到相机</p>
          <p className="text-sm text-gray-500 mt-2">请确保相机已连接并配置正确</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cameras.map((camera) => (
            <CameraCard
              key={camera.serial_number}
              camera={camera}
              onStart={() => handleStartCamera(camera.serial_number)}
              onStop={() => handleStopCamera(camera.serial_number)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface CameraCardProps {
  camera: CameraInfo
  onStart: () => void
  onStop: () => void
}

function CameraCard({ camera, onStart, onStop }: CameraCardProps) {
  const isRunning = camera.status === 'running'

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center space-x-3">
          <div className={`w-3 h-3 rounded-full ${isRunning ? 'bg-green-500' : 'bg-gray-600'}`} />
          <div>
            <h3 className="font-semibold">{camera.name}</h3>
            <p className="text-sm text-gray-400">{camera.model}</p>
          </div>
        </div>
      </div>

      <div className="space-y-2 mb-4">
        <InfoItem label="序列号" value={camera.serial_number} />
        <InfoItem label="分辨率" value={camera.resolution} />
        <InfoItem label="帧率" value={`${camera.fps} FPS`} />
        <InfoItem label="状态" value={camera.status} />
      </div>

      <div className="flex space-x-2">
        {isRunning ? (
          <button
            onClick={onStop}
            className="flex-1 flex items-center justify-center space-x-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
          >
            <Square className="w-4 h-4" />
            <span>停止</span>
          </button>
        ) : (
          <button
            onClick={onStart}
            className="flex-1 flex items-center justify-center space-x-2 px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
          >
            <Play className="w-4 h-4" />
            <span>启动</span>
          </button>
        )}
      </div>
    </div>
  )
}

interface InfoItemProps {
  label: string
  value: string
}

function InfoItem({ label, value }: InfoItemProps) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  )
}
