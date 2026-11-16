import { t } from '@/i18n/core'
export function documentStatusLabel(status: string) {
  return ({ draft: t('Черновик'), pending: t('На проверке'), approved: t('Документы проверены'), rejected: t('На исправлении'), superseded: t('Предыдущая версия'), legacy: t('Ранее одобрен, документы ещё не предоставлены'), missing: t('Нужны документы') } as Record<string, string>)[status] ?? status
}
