import { lazy, Suspense, useState } from 'react'
import { FileText, Upload } from 'lucide-react'
import { Button, Skeleton, StatusPill } from '@/components/ui-kit'
import type { DocumentsSummary, DriverDocument, DocumentKind } from '@/hooks/use-documents'
import { t, useLocale, getIntlLocale } from '@/i18n/core'
import { formatDateTime } from '@/lib/format'
const PdfViewer = lazy(() => import('./PdfViewer'))

export function DocumentCards({
  data,
  editable = false,
  busy = false,
  onUpload,
  onDelete,
}: {
  data: DocumentsSummary
  editable?: boolean
  busy?: boolean
  onUpload?: (kind: DocumentKind, file: File) => void
  onDelete?: (kind: DocumentKind) => void
}) {
  useLocale()
  const [viewing, setViewing] = useState<DriverDocument | null>(null)
  return (
    <>
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))' }}
      >
        {(['identity_card', 'driver_license'] as const).map((kind) => {
          const doc = data.documents.find((item) => item.kind === kind)
          return (
            <section
              key={kind}
              className="flex min-w-0 flex-col gap-3 rounded-lg border border-border-default bg-bg-canvas p-4"
            >
              <div className="flex items-center gap-2">
                <FileText className="size-5 text-text-secondary" />
                <h3 className="text-body-medium">
                  {t(kind === 'identity_card' ? 'Удостоверение личности' : 'Водительские права')}
                </h3>
              </div>
              {doc ? (
                <>
                  <p className="break-all text-callout">{doc.filename}</p>
                  <p className="text-caption text-text-secondary">
                    {new Intl.NumberFormat(getIntlLocale(), { maximumFractionDigits: 2 }).format(
                      doc.size_bytes < 1048576
                        ? Math.max(1, Math.round(doc.size_bytes / 1024))
                        : doc.size_bytes / 1048576,
                    )}{' '}
                    {doc.size_bytes < 1048576 ? 'KB' : 'MB'} · {doc.page_count} {t('стр.')}
                    <br />
                    {formatDateTime(doc.created_at)}
                  </p>
                  <StatusPill tone="success">{t('Загружен')}</StatusPill>
                  <Button variant="secondary" size="md" onClick={() => setViewing(doc)}>
                    {t('Посмотреть')}
                  </Button>
                </>
              ) : (
                <p className="text-callout text-text-secondary">{t('Файл ещё не загружен')}</p>
              )}
              {editable && (
                <div className="mt-auto flex flex-wrap gap-2">
                  <label
                    className={`inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md bg-bg-muted px-3 text-callout focus-within:ring-2 ${busy ? 'pointer-events-none opacity-50' : ''}`}
                  >
                    <Upload className="size-4" />
                    <span>{t(doc ? 'Заменить' : 'Загрузить')}</span>
                    <input
                      className="sr-only"
                      type="file"
                      accept="application/pdf,.pdf"
                      disabled={busy}
                      aria-label={t(
                        kind === 'identity_card' ? 'Загрузить удостоверение' : 'Загрузить права',
                      )}
                      onChange={(event) => {
                        const file = event.target.files?.[0]
                        if (file) onUpload?.(kind, file)
                        event.target.value = ''
                      }}
                    />
                  </label>
                  {doc && (
                    <Button
                      variant="ghost"
                      size="md"
                      disabled={busy}
                      onClick={() => onDelete?.(kind)}
                    >
                      {t('Удалить')}
                    </Button>
                  )}
                </div>
              )}
            </section>
          )
        })}
      </div>
      {viewing && (
        <Suspense
          fallback={
            <div className="fixed inset-8 z-50 bg-bg-canvas p-6">
              <Skeleton className="h-40" />
              <Button onClick={() => setViewing(null)}>{t('Закрыть')}</Button>
            </div>
          }
        >
          <PdfViewer
            key={viewing.id}
            id={viewing.id}
            filename={viewing.filename}
            onClose={() => setViewing(null)}
          />
        </Suspense>
      )}
    </>
  )
}
