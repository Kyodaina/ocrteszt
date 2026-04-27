import { ImageTask } from '../lib/types'

const statusColor: Record<string, string> = {
  queued: 'bg-zinc-500',
  loading: 'bg-blue-500',
  preprocessing: 'bg-indigo-500',
  ocr_running: 'bg-yellow-500',
  semantic_analysis: 'bg-purple-500',
  completed: 'bg-emerald-500',
  failed: 'bg-red-500',
}

export default function TaskTable({ tasks, onRetry }: { tasks: ImageTask[]; onRetry: (id: string) => void }) {
  return (
    <div className="rounded-2xl border border-zinc-700 overflow-hidden">
      <div className="max-h-[420px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="bg-white/10 sticky top-0">
            <tr>
              <th className="p-3 text-left">File</th><th className="p-3">Status</th><th className="p-3">Intent</th><th className="p-3">Importance</th><th className="p-3">Confidence</th><th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.file_id} className="border-t border-zinc-800">
                <td className="p-3 max-w-[240px] truncate" title={t.filename}>{t.filename}</td>
                <td className="p-3"><span className={`px-2 py-1 rounded text-xs text-black ${statusColor[t.status] ?? 'bg-zinc-500'}`}>{t.processing_status}</span></td>
                <td className="p-3">{t.marketing_intent}</td>
                <td className="p-3 text-center">{t.importance_score}</td>
                <td className="p-3 text-center">{Math.round(t.confidence_score * 100)}%</td>
                <td className="p-3 text-center">{t.status === 'failed' ? <button className="underline" onClick={() => onRetry(t.file_id)}>Retry</button> : '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
