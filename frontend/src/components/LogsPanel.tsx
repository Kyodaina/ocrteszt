export interface LogEntry {
  ts: string
  level: 'info' | 'warning' | 'error'
  message: string
  file_id?: string
  trace?: string
}

export default function LogsPanel({ logs }: { logs: LogEntry[] }) {
  return (
    <div className="rounded-2xl border border-zinc-700 p-3 h-[240px] overflow-auto text-xs font-mono bg-black/40">
      {logs.map((log, idx) => (
        <div key={idx} className="mb-2">
          <span className="text-zinc-400">[{new Date(log.ts).toLocaleTimeString()}]</span>{' '}
          <span className={log.level === 'error' ? 'text-red-400' : log.level === 'warning' ? 'text-yellow-400' : 'text-emerald-400'}>{log.level.toUpperCase()}</span>{' '}
          <span>{log.message}</span>
          {log.trace && <pre className="whitespace-pre-wrap text-red-300">{log.trace}</pre>}
        </div>
      ))}
    </div>
  )
}
