export type Stage =
  | 'queued'
  | 'loading'
  | 'preprocessing'
  | 'ocr_running'
  | 'semantic_analysis'
  | 'completed'
  | 'failed'

export interface ImageTask {
  file_id: string
  filename: string
  path: string
  size: number
  sha256: string
  status: Stage
  processing_status: string
  visible_text: string
  marketing_intent: string
  importance_score: number
  confidence_score: number
  error?: string
}

export interface GlobalProgress {
  total_files: number
  completed_files: number
  failed_files: number
  estimated_remaining_seconds: number
}
