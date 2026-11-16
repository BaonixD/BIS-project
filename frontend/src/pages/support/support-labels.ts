import { t } from '@/i18n/core'
export const supportCategory = (value: string) =>
  (
    ({
      ride: t('Поездка'),
      payment: t('Оплата'),
      documents: t('Документы'),
      account: t('Аккаунт'),
      other: t('Другое'),
    }) as Record<string, string>
  )[value] ?? value
export const supportStatus = (value: string) =>
  (
    ({ open: t('Открыто'), in_progress: t('В работе'), resolved: t('Решено') }) as Record<
      string,
      string
    >
  )[value] ?? value
