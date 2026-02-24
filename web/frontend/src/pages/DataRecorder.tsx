import { useState } from 'react'
import { Play, Square, Database } from 'lucide-react'

export default function DataRecorder() {
  const [isRecording, setIsRecording] = useState(false)
  const [experimentName, setExperimentName] = useState('')

  const handleStartRecording = async () => {
    try {
      await fetch('/api/recording/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ experiment_name: experimentName }),
      })
      setIsRecording(true)
    } catch (err) {
      console.error('启动录制失败:', err)
    }
  }

  const handleStopRecording = async () => {
    try {
      await fetch('/api/recording/stop', { method: 'POST' })
      setIsRecording(false)
      setExperimentName('')
    } catch (err) {
      console.error('停止录制失败:', err)
    }
  }

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">数据记录</h1>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-6">
        <h2 className="text-xl font-semibold mb-4">录制控制</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">实验名称</label>
            <input
              type="text"
              value={experimentName}
              onChange={(e) => setExperimentName(e.target.value)}
              placeholder="输入实验名称（可选）"
              disabled={isRecording}
              className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:outline-none focus:border-primary-500 disabled:opacity-50"
            />
          </div>

          <div className="flex space-x-4">
            {!isRecording ? (
              <button
                onClick={handleStartRecording}
                className="flex items-center space-x-2 px-6 py-3 bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
              >
                <Play className="w-5 h-5" />
                <span>开始录制</span>
              </button>
            ) : (
              <button
                onClick={handleStopRecording}
                className="flex items-center space-x-2 px-6 py-3 bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
              >
                <Square className="w-5 h-5" />
                <span>停止录制</span>
              </button>
            )}
          </div>

          {isRecording && (
            <div className="flex items-center space-x-2 text-red-500">
              <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
              <span>正在录制...</span>
            </div>
          )}
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold mb-4">历史记录</h2>
        <div className="text-center py-12 text-gray-400">
          <Database className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>暂无录制数据</p>
        </div>
      </div>
    </div>
  )
}
