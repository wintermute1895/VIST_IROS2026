import { Settings } from 'lucide-react'

export default function SystemSettings() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-8">系统设置</h1>

      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold mb-4">VIST参数</h2>
        <div className="space-y-4">
          <SettingItem label="控制频率" value="60 Hz" />
          <SettingItem label="IK策略" value="VIST" />
          <SettingItem label="意图检测" value="启用" />
          <SettingItem label="几何求解器" value="启用" />
        </div>
      </div>

      <div className="mt-6 bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h2 className="text-xl font-semibold mb-4">关于</h2>
        <div className="space-y-2 text-gray-400">
          <p>VIST 遥操作系统 v1.0.0</p>
          <p>© 2026 VIST Project</p>
        </div>
      </div>
    </div>
  )
}

interface SettingItemProps {
  label: string
  value: string
}

function SettingItem({ label, value }: SettingItemProps) {
  return (
    <div className="flex justify-between items-center py-3 border-b border-gray-700">
      <span className="text-gray-400">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  )
}
