import { useState } from 'react'
import { Dialog } from 'radix-ui'
import { DocumentCards } from './DocumentCards'
import { useDocuments, useDocumentAction } from '@/hooks/use-documents'
import { documentStatusLabel } from '@/lib/document-labels'
import { Button, Skeleton, StatusPill } from '@/components/ui-kit'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { t, useLocale } from '@/i18n/core'

export function AdminDocuments({ driverId }: { driverId: string }) {
  useLocale()
  const [selected, setSelected] = useState('')
  const query = useDocuments(driverId, selected || undefined)
  const action = useDocumentAction(driverId)
  const [mode, setMode] = useState<'reject' | 'request' | null>(null)
  const [reason, setReason] = useState('')
  const data = query.data
  const pkg = data?.package
  const close = () => { if (!action.isPending) { setMode(null); setReason(''); action.reset() } }
  return <section className="flex w-full flex-col gap-4 rounded-lg bg-bg-subtle p-4"><h2 className="text-headline">{t('Пакет документов')}</h2><ErrorAlert error={query.error} />{query.isPending && <Skeleton className="h-32" />}
    {data && <><div className="flex flex-wrap items-center gap-2"><StatusPill>{documentStatusLabel(pkg?.status ?? (data.legacy_exempt ? 'legacy' : 'missing'))}</StatusPill>{pkg && <span className="text-caption">{t('Версия')} {pkg.version}</span>}<Button variant="ghost" size="md" onClick={() => void query.refetch()}>{t('Обновить')}</Button></div>{pkg?.review_note && <p className="text-callout">{pkg.review_note}</p>}
      {(data.history ?? []).length > 0 && <label className="text-caption">{t('Версии пакета')}<select className="ml-2 rounded-md border border-border-default bg-bg-canvas p-2" value={selected} onChange={(event) => setSelected(event.target.value)}><option value="">{t('Текущая версия')}</option>{(data.history ?? []).map((item) => <option key={item.id} value={item.id}>{item.version} · {documentStatusLabel(item.status)}</option>)}</select></label>}
      <DocumentCards data={data} />
      {pkg?.status === 'pending' && !selected && <Button variant="danger" size="md" onClick={() => setMode('reject')}>{t('Вернуть на исправление')}</Button>}
      {data.legacy_exempt && <Button variant="secondary" size="md" onClick={() => setMode('request')}>{t('Запросить документы')}</Button>}
    </>}
    <Dialog.Root open={mode !== null} onOpenChange={(open) => { if (!open) close() }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" /><Dialog.Content className="fixed top-1/2 left-1/2 z-50 flex w-[calc(100%-32px)] max-w-md -translate-x-1/2 -translate-y-1/2 flex-col gap-4 rounded-xl bg-bg-canvas p-6"><Dialog.Title className="text-headline">{t(mode === 'reject' ? 'Вернуть на исправление' : 'Запросить документы')}</Dialog.Title><Dialog.Description className="text-callout text-text-secondary">{t('Укажите, что нужно исправить или загрузить.')}</Dialog.Description><form className="flex flex-col gap-3" onSubmit={(event) => { event.preventDefault(); if (mode === 'reject' && pkg) action.mutate({ type: 'reject', package: pkg, reason: reason.trim() }, { onSuccess: () => { setMode(null); setReason('') } }); if (mode === 'request') action.mutate({ type: 'request', reason: reason.trim() }, { onSuccess: () => { setMode(null); setReason('') } }) }}><textarea aria-label={t('Причина')} required minLength={3} maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} className="min-h-28 rounded-md border border-border-default p-3" /><ErrorAlert error={action.error} /><Button type="submit" loading={action.isPending} disabled={reason.trim().length < 3}>{t('Отправить')}</Button><Button variant="ghost" size="md" disabled={action.isPending} onClick={close}>{t('Отмена')}</Button></form></Dialog.Content></Dialog.Portal></Dialog.Root>
  </section>
}
