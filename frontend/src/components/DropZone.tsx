import { Upload } from 'lucide-react'
import { motion } from 'framer-motion'
import { useRef } from 'react'

interface Props {
  onFiles: (files: File[]) => void
}

async function collectFromItems(items: DataTransferItemList): Promise<File[]> {
  const out: File[] = []
  const walk = async (entry: any): Promise<void> => {
    if (entry.isFile) {
      await new Promise<void>((resolve) => {
        entry.file((file: File) => {
          out.push(file)
          resolve()
        })
      })
      return
    }
    if (entry.isDirectory) {
      const reader = entry.createReader()
      await new Promise<void>((resolve) => {
        reader.readEntries(async (entries: any[]) => {
          for (const e of entries) await walk(e)
          resolve()
        })
      })
    }
  }

  for (const item of Array.from(items)) {
    const entry = (item as any).webkitGetAsEntry?.()
    if (entry) await walk(entry)
    else {
      const f = item.getAsFile()
      if (f) out.push(f)
    }
  }
  return out
}

export default function DropZone({ onFiles }: Props) {
  const fileInput = useRef<HTMLInputElement>(null)
  const folderInput = useRef<HTMLInputElement>(null)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl border border-zinc-700 p-8 text-center bg-white/5 backdrop-blur"
      onDragOver={(e) => e.preventDefault()}
      onDrop={async (e) => {
        e.preventDefault()
        const files = await collectFromItems(e.dataTransfer.items)
        onFiles(files)
      }}
    >
      <Upload className="mx-auto mb-3" />
      <p className="text-lg">Drag & drop images or folders</p>
      <p className="text-sm text-zinc-400 mb-4">Supports massive local batches with live pipeline tracking.</p>
      <div className="flex gap-2 justify-center">
        <button className="px-3 py-2 rounded bg-white text-black" onClick={() => fileInput.current?.click()}>Choose Images</button>
        <button className="px-3 py-2 rounded border border-zinc-500" onClick={() => folderInput.current?.click()}>Choose Folder</button>
      </div>
      <input
        ref={fileInput}
        className="hidden"
        type="file"
        accept="image/*"
        multiple
        onChange={(e) => onFiles(Array.from(e.target.files ?? []))}
      />
      <input
        ref={folderInput}
        className="hidden"
        type="file"
        // @ts-expect-error webkitdirectory
        webkitdirectory=""
        multiple
        onChange={(e) => onFiles(Array.from(e.target.files ?? []))}
      />
    </motion.div>
  )
}
