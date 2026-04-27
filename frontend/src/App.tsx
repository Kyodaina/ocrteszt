import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import DropZone from './components/DropZone'
import TaskTable from './components/TaskTable'
import LogsPanel, { LogEntry } from './components/LogsPanel'
import { GlobalProgress, ImageTask } from './lib/types'

const sorters = {
  importance: (a: ImageTask, b: ImageTask) => b.importance_score - a.importance_score,
  confidence: (a: ImageTask, b: ImageTask) => b.confidence_score - a.confidence_score,
}

export default function App() {
  const [tasks, setTasks] = useState<ImageTask[]>([])
  const [global, setGlobal] = useState<GlobalProgress>({ total_files: 0, completed_files: 0, failed_files: 0, estimated_remaining_seconds: 0 })
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [query, setQuery] = useState('')
  const [sortBy, setSortBy] = useState<'importance' | 'confidence'>('importance')
  const [dark, setDark] = useState(true)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
  }, [dark])

  useEffect(() => {
    fetch('/api/snapshot').then((r) => r.json()).then((data) => {
      setTasks(data.tasks)
      setGlobal(data.global)
    })

    const ws = new WebSocket(`ws://${window.location.host}/ws`)
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.kind === 'file_update') {
        setTasks((prev) => {
          const i = prev.findIndex((x) => x.file_id === msg.payload.file_id)
          if (i === -1) return [msg.payload, ...prev]
          const copy = [...prev]
          copy[i] = msg.payload
          return copy
        })
      } else if (msg.kind === 'global') setGlobal(msg.payload)
      else if (msg.kind === 'log') setLogs((prev) => [msg.payload, ...prev].slice(0, 500))
      else if (msg.kind === 'snapshot') {
        setTasks(msg.payload.tasks)
        setGlobal(msg.payload.global)
      }
    }
    return () => ws.close()
  }, [])

  const uploadFiles = async (files: File[]) => {
    if (!files.length) return
    const form = new FormData()
    files.forEach((f) => form.append('files', f, f.webkitRelativePath || f.name))
    await fetch('/api/upload', { method: 'POST', body: form })
    await fetch('/api/process/start', { method: 'POST' })
  }

  const retry = async (id: string) => {
    await fetch(`/api/process/retry/${id}`, { method: 'POST' })
  }

  const filtered = useMemo(() => tasks
    .filter((t) => t.filename.toLowerCase().includes(query.toLowerCase()) || t.visible_text.toLowerCase().includes(query.toLowerCase()))
    .sort(sorters[sortBy]), [tasks, query, sortBy])

  const progress = global.total_files ? ((global.completed_files + global.failed_files) / global.total_files) * 100 : 0

  return (
    <div className="min-h-screen bg-paper text-ink dark:bg-ink dark:text-paper transition-colors duration-300">
      <main className="max-w-7xl mx-auto p-4 md:p-8 space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Local-first OCR + Semantic Analysis</h1>
          <button className="border rounded px-3 py-1" onClick={() => setDark((v) => !v)}>{dark ? 'Light' : 'Dark'} mode</button>
        </div>

        <DropZone onFiles={uploadFiles} />

        <motion.div className="rounded-xl border border-zinc-700 p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
          <div className="flex flex-wrap gap-4 text-sm">
            <span>Total: {global.total_files}</span>
            <span>Completed: {global.completed_files}</span>
            <span>Failed: {global.failed_files}</span>
            <span>ETA: {global.estimated_remaining_seconds}s</span>
          </div>
          <div className="mt-3 h-2 w-full bg-zinc-700 rounded overflow-hidden">
            <div className="h-full bg-white dark:bg-zinc-100 transition-all duration-500" style={{ width: `${progress}%` }} />
          </div>
        </motion.div>

        <div className="grid lg:grid-cols-3 gap-5">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex gap-2">
              <input className="flex-1 bg-transparent border border-zinc-600 rounded px-3 py-2" placeholder="Search filename or text" value={query} onChange={(e) => setQuery(e.target.value)} />
              <select className="border border-zinc-600 bg-transparent rounded px-2" value={sortBy} onChange={(e) => setSortBy(e.target.value as any)}>
                <option value="importance">Sort: Importance</option>
                <option value="confidence">Sort: Confidence</option>
              </select>
              <a className="border rounded px-2 py-2" href="/api/export/csv">CSV</a>
              <a className="border rounded px-2 py-2" href="/api/export/xlsx">XLSX</a>
              <a className="border rounded px-2 py-2" href="/api/export/pdf">PDF</a>
            </div>
            <TaskTable tasks={filtered} onRetry={retry} />
          </div>
          <LogsPanel logs={logs} />
        </div>

        <section className="grid grid-cols-2 md:grid-cols-6 gap-2">
          {filtered.slice(0, 48).map((t) => (
            <div key={t.file_id} className="rounded border border-zinc-700 p-1 text-xs">
              <img src={`/${t.path.replace(/\\/g, '/')}`} loading="lazy" className="h-20 w-full object-cover rounded" />
              <div className="truncate mt-1" title={t.filename}>{t.filename}</div>
            </div>
          ))}
        </section>
      </main>
    </div>
  )
}
