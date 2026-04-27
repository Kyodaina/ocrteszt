import { motion } from 'framer-motion'
import { useEffect, useMemo, useRef, useState } from 'react'

type Stage = 'queued' | 'loading' | 'preprocessing' | 'OCR running' | 'semantic analysis' | 'completed' | 'failed'

type Task = {
  id: string
  filename: string
  stage: Stage
  duplicate_of?: string | null
  retries: number
  error?: string | null
  result?: {
    visible_text: string
    marketing_intent: string
    importance_score: number
    confidence_score: number
  } | null
}

type Stats = {
  total_files: number
  completed_files: number
  failed_files: number
  queued_files: number
  estimated_remaining_seconds: number
}

type Log = { timestamp: string; level: string; message: string; task_id?: string; stack_trace?: string }

const stageProgress: Record<Stage, number> = {
  queued: 8,
  loading: 20,
  preprocessing: 35,
  'OCR running': 60,
  'semantic analysis': 82,
  completed: 100,
  failed: 100,
}

export function App() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [stats, setStats] = useState<Stats>({ total_files: 0, completed_files: 0, failed_files: 0, queued_files: 0, estimated_remaining_seconds: 0 })
  const [logs, setLogs] = useState<Log[]>([])
  const [query, setQuery] = useState('')
  const [sortBy, setSortBy] = useState<'importance' | 'confidence' | 'name'>('importance')
  const [dark, setDark] = useState(true)
  const [wsConnected, setWsConnected] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    fetch('/api/tasks').then((r) => r.json()).then((data) => {
      setTasks(data.tasks ?? [])
      setStats(data.stats ?? stats)
      setLogs(data.logs ?? [])
    })

    const ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`)
    ws.onopen = () => setWsConnected(true)
    ws.onclose = () => setWsConnected(false)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'snapshot') {
        setTasks(msg.payload.tasks ?? [])
        setStats(msg.payload.stats ?? stats)
        setLogs(msg.payload.logs ?? [])
      } else if (msg.type === 'task') {
        setTasks((prev) => {
          const idx = prev.findIndex((t) => t.id === msg.payload.id)
          if (idx === -1) return [msg.payload, ...prev]
          const copy = [...prev]
          copy[idx] = msg.payload
          return copy
        })
      } else if (msg.type === 'stats') {
        setStats(msg.payload)
      } else if (msg.type === 'log') {
        setLogs((prev) => [msg.payload, ...prev].slice(0, 500))
      }
    }
    return () => ws.close()
  }, [])

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim()
    const f = tasks.filter((t) => !q || t.filename.toLowerCase().includes(q) || (t.result?.visible_text || '').toLowerCase().includes(q))
    return f.sort((a, b) => {
      if (sortBy === 'name') return a.filename.localeCompare(b.filename)
      if (sortBy === 'confidence') return (b.result?.confidence_score ?? 0) - (a.result?.confidence_score ?? 0)
      return (b.result?.importance_score ?? 0) - (a.result?.importance_score ?? 0)
    })
  }, [tasks, query, sortBy])

  async function uploadFiles(fileList: FileList | null) {
    if (!fileList?.length) return
    const fd = new FormData()
    for (const file of Array.from(fileList)) fd.append('files', file)
    await fetch('/api/queue', { method: 'POST', body: fd })
  }

  const cls = dark ? 'bg-black text-white' : 'bg-white text-black'

  return (
    <div className={`${cls} min-h-screen transition-colors`}>
      <div className="mx-auto max-w-7xl p-4 md:p-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl md:text-4xl font-semibold tracking-tight">Bulk OCR + Semantic Analyzer</h1>
            <p className="text-sm opacity-70">Local-first • Qwen 2.5 VL • Real-time pipeline monitoring</p>
          </div>
          <div className="flex gap-2">
            <button className="rounded border border-current px-3 py-1 text-sm" onClick={() => setDark((d) => !d)}>{dark ? 'Light' : 'Dark'} Mode</button>
            <span className={`rounded px-3 py-1 text-xs ${wsConnected ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>{wsConnected ? 'Live' : 'Disconnected'}</span>
          </div>
        </header>

        <section
          className="mb-6 rounded-2xl border border-white/20 p-6 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); uploadFiles(e.dataTransfer.files) }}
        >
          <p className="mb-3 text-lg">Drag & drop images/folders here</p>
          <div className="flex flex-wrap justify-center gap-2">
            <button className="rounded bg-white text-black px-4 py-2" onClick={() => inputRef.current?.click()}>Choose Files</button>
            <button className="rounded border border-current px-4 py-2" onClick={() => document.getElementById('folder-input')?.click()}>Choose Folder</button>
            <button className="rounded border border-current px-4 py-2" onClick={() => window.open('/api/export/json')}>Export JSON</button>
            <button className="rounded border border-current px-4 py-2" onClick={() => window.open('/api/export/csv')}>Export CSV</button>
            <button className="rounded border border-current px-4 py-2" onClick={() => window.open('/api/export/xlsx')}>Export XLSX</button>
          </div>
          <input ref={inputRef} type="file" multiple accept="image/*" className="hidden" onChange={(e) => uploadFiles(e.target.files)} />
          <input id="folder-input" type="file" multiple {...({ webkitdirectory: 'true', directory: 'true' } as any)} className="hidden" onChange={(e) => uploadFiles(e.target.files)} />
        </section>

        <section className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            ['Total', stats.total_files],
            ['Completed', stats.completed_files],
            ['Failed', stats.failed_files],
            ['ETA (s)', Math.ceil(stats.estimated_remaining_seconds || 0)],
          ].map(([label, value]) => (
            <motion.div key={String(label)} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="rounded-xl border border-white/20 p-4">
              <div className="text-xs opacity-70">{label}</div>
              <div className="text-2xl font-semibold">{String(value)}</div>
            </motion.div>
          ))}
        </section>

        <section className="mb-4 flex flex-wrap gap-2">
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search filename/text" className="rounded border border-current bg-transparent px-3 py-2 text-sm" />
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value as any)} className="rounded border border-current bg-transparent px-3 py-2 text-sm">
            <option value="importance">Sort: Importance</option>
            <option value="confidence">Sort: Confidence</option>
            <option value="name">Sort: Name</option>
          </select>
        </section>

        <section className="grid gap-3">
          {filtered.map((task) => (
            <div key={task.id} className="rounded-xl border border-white/20 p-4">
              <div className="mb-2 flex items-center justify-between gap-4">
                <div className="truncate font-medium" title={task.filename}>{task.filename}</div>
                <span className={`text-xs rounded px-2 py-1 ${task.stage === 'completed' ? 'bg-green-600 text-white' : task.stage === 'failed' ? 'bg-red-600 text-white' : 'bg-white text-black'}`}>{task.stage}</span>
              </div>
              <div className="h-2 w-full rounded bg-white/10 overflow-hidden mb-2">
                <motion.div initial={{ width: 0 }} animate={{ width: `${stageProgress[task.stage]}%` }} className={`h-2 ${task.stage === 'failed' ? 'bg-red-500' : 'bg-white'}`} />
              </div>
              {task.result ? (
                <div className="grid md:grid-cols-4 gap-2 text-sm">
                  <div><b>Intent:</b> {task.result.marketing_intent}</div>
                  <div><b>Importance:</b> {task.result.importance_score}</div>
                  <div><b>Confidence:</b> {(task.result.confidence_score * 100).toFixed(1)}%</div>
                  <div className="truncate"><b>Duplicate:</b> {task.duplicate_of ?? '-'}</div>
                  <pre className="md:col-span-4 whitespace-pre-wrap break-words rounded bg-white/5 p-2 max-h-56 overflow-auto">{task.result.visible_text || '(no text)'}</pre>
                </div>
              ) : (
                <div className="animate-pulse h-12 rounded bg-white/10" />
              )}
              {task.error && <div className="mt-2 text-red-400 text-xs">{task.error} <button className="underline" onClick={() => fetch(`/api/retry/${task.id}`, { method: 'POST' })}>Retry</button></div>}
            </div>
          ))}
        </section>

        <section className="mt-8 rounded-xl border border-white/20 p-4">
          <h2 className="mb-3 font-semibold">Live Logs</h2>
          <div className="max-h-64 overflow-auto text-xs space-y-2">
            {logs.map((l, idx) => (
              <div key={idx} className="border-b border-white/10 pb-1">
                <span className="opacity-70">[{new Date(l.timestamp).toLocaleTimeString()}]</span> <b className={l.level === 'error' ? 'text-red-400' : l.level === 'warning' ? 'text-yellow-400' : 'text-green-400'}>{l.level.toUpperCase()}</b> {l.message}
                {l.stack_trace && <pre className="mt-1 whitespace-pre-wrap text-red-300">{l.stack_trace}</pre>}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
