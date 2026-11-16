import { Link } from 'react-router'
import { CheckCircle2, Circle } from 'lucide-react'
import { BackHeader } from '@/components/driver/BackHeader'
import { Screen, ScreenColumn } from '@/components/driver/Screen'
import { ErrorAlert } from '@/components/common/ErrorAlert'
import { Button, Skeleton, StatusPill } from '@/components/ui-kit'
import { DocumentCards } from '@/components/documents/DocumentCards'
import { useDocuments, useDocumentAction } from '@/hooks/use-documents'
import { t, useLocale } from '@/i18n/core'
import { documentStatusLabel } from '@/lib/document-labels'

export function DriverDocumentsPage() {
  useLocale()
  const query = useDocuments()
  const action = useDocumentAction()
  const data = query.data
  const pkg = data?.package
  const editable = !pkg || pkg.status === 'draft'
  return <Screen tone="subtle" overNav><ScreenColumn className="gap-5 pt-[calc(56px+env(safe-area-inset-top))] pb-8 lg:max-w-3xl lg:pt-8"><BackHeader title={t('Документы')} fallback="/driver/profile" /><p className="text-callout text-text-secondary">{t('Загрузите удостоверение и права. PDF, до 10 МБ и 10 страниц; обе стороны в одном файле.')}</p><ErrorAlert error={query.error} />{query.isPending && <Skeleton className="h-40 w-full" />}
    {data && <><div className="flex flex-wrap items-center gap-2"><StatusPill tone={pkg?.status === 'approved' ? 'success' : pkg?.status === 'rejected' ? 'danger' : 'warning'}>{documentStatusLabel(pkg?.status ?? (data.legacy_exempt ? 'legacy' : 'missing'))}</StatusPill>{pkg && <span className="text-caption text-text-secondary">{t('Версия')} {pkg.version}</span>}</div>{pkg?.review_note && <p className="rounded-md bg-bg-canvas p-4 text-callout">{pkg.review_note}</p>}
      <div className="rounded-lg bg-bg-canvas p-4"><p className="mb-3 text-body-medium">{t('Готовность к проверке')}</p>{[[t('Профиль и машина заполнены'), data.missing_fields.length === 0], [t('Удостоверение личности'), data.documents.some((item) => item.kind === 'identity_card')], [t('Водительские права'), data.documents.some((item) => item.kind === 'driver_license')]].map(([label, complete]) => <p key={String(label)} className="flex items-center gap-2 py-1 text-callout">{complete ? <CheckCircle2 className="size-4 text-accent-success" /> : <Circle className="size-4 text-text-tertiary" />}{label}</p>)}{data.missing_fields.length > 0 && <Link to="/driver/settings" className="mt-2 inline-block text-callout underline">{t('Заполнить профиль')}</Link>}</div>
      <DocumentCards data={data} editable={editable} busy={action.isPending} onUpload={(kind, file) => action.mutate({ type: 'upload', kind, file })} onDelete={(kind) => action.mutate({ type: 'delete', kind })} />
      <ErrorAlert error={action.error} />{action.isPending && <p role="status" className="text-caption">{t('Сохраняем документы…')}</p>}
      {pkg && editable && <Button className="w-full" disabled={!data.can_submit} loading={action.isPending} onClick={() => action.mutate({ type: 'submit', package: pkg })}>{t('Отправить на проверку')}</Button>}
      {pkg && !editable && <Button variant="secondary" loading={action.isPending} onClick={() => action.mutate({ type: 'revise', package: pkg })}>{t('Исправить документы')}</Button>}
    </>}
  </ScreenColumn></Screen>
}
