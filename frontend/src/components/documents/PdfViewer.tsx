import { useEffect, useRef, useState } from 'react'
import { Dialog } from 'radix-ui'
import { getDocument, GlobalWorkerOptions, type PDFDocumentProxy } from 'pdfjs-dist'
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { Button } from '@/components/ui-kit'
import { t, useLocale } from '@/i18n/core'

GlobalWorkerOptions.workerSrc = workerUrl

export default function PdfViewer({ id, filename, onClose }: { id: string; filename: string; onClose: () => void }) {
  useLocale()
  const canvas = useRef<HTMLCanvasElement>(null)
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null)
  const [page, setPage] = useState(1)
  const [scale, setScale] = useState(1)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    const controller = new AbortController()
    let destroyed = false
    let task: ReturnType<typeof getDocument> | undefined
    void (async () => {
      const response = await fetch(`/api/v1/documents/${id}/content`, { credentials: 'include', signal: controller.signal, cache: 'no-store' })
      if (!response.ok) throw new Error('PDF unavailable')
      task = getDocument({ data: await response.arrayBuffer(), isEvalSupported: false })
      const pdf = await task.promise
      if (!destroyed) setDocument(pdf)
    })().catch(() => { if (!destroyed) { setError(true); setLoading(false) } })
    return () => { destroyed = true; controller.abort(); void task?.destroy() }
  }, [id])
  useEffect(() => {
    if (!document) return
    let cancelled = false
    let render: ReturnType<Awaited<ReturnType<PDFDocumentProxy['getPage']>>['render']> | undefined
    setLoading(true)
    void document.getPage(page).then((pdfPage) => {
      if (cancelled || !canvas.current) return
      const viewport = pdfPage.getViewport({ scale })
      const node = canvas.current
      node.width = viewport.width
      node.height = viewport.height
      render = pdfPage.render({ canvas: node, viewport })
      return render.promise
    }).then(() => { if (!cancelled) setLoading(false) }).catch(() => { if (!cancelled) { setError(true); setLoading(false) } })
    return () => { cancelled = true; render?.cancel() }
  }, [document, page, scale])
  return <Dialog.Root open onOpenChange={(open) => { if (!open) onClose() }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" /><Dialog.Content className="fixed inset-3 z-50 flex flex-col gap-3 rounded-lg bg-bg-canvas p-4 shadow-sheet sm:inset-8 lg:inset-x-[15%]">
    <div className="flex items-center justify-between gap-2"><Dialog.Title className="min-w-0 truncate text-headline">{filename}</Dialog.Title><Button variant="ghost" size="md" onClick={onClose}>{t('Закрыть')}</Button></div>
    <Dialog.Description className="sr-only">{t('Просмотр PDF')}</Dialog.Description>
    <div className="flex flex-wrap items-center gap-2"><Button size="md" variant="secondary" disabled={!document || page <= 1} onClick={() => setPage(page - 1)}>{t('Назад')}</Button><span className="text-caption">{page} / {document?.numPages ?? '—'}</span><Button size="md" variant="secondary" disabled={!document || page >= document.numPages} onClick={() => setPage(page + 1)}>{t('Вперёд')}</Button><Button size="md" variant="ghost" disabled={scale <= 0.5} onClick={() => setScale(Math.max(0.5, scale - 0.25))} aria-label={t('Уменьшить масштаб')}>−</Button><Button size="md" variant="ghost" disabled={scale >= 2} onClick={() => setScale(Math.min(2, scale + 0.25))} aria-label={t('Увеличить масштаб')}>+</Button><a className="text-callout underline" href={`/api/v1/documents/${id}/content`}>{t('Скачать PDF')}</a></div>
    <div className="min-h-0 flex-1 overflow-auto rounded-md bg-bg-subtle p-2" aria-busy={loading}>{loading && <p role="status">{t('Загрузка…')}</p>}{error && <p role="alert">{t('Не удалось открыть PDF. Скачайте файл.')}</p>}<canvas ref={canvas} className="mx-auto max-w-full" aria-label={t('Страница документа')} /></div>
  </Dialog.Content></Dialog.Portal></Dialog.Root>
}
