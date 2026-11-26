import {
  Car,
  Compass,
  CreditCard,
  Flag,
  Flame,
  Gem,
  Heart,
  MessageCircle,
  Moon,
  PiggyBank,
  Repeat,
  Route,
  Sparkles,
  Star,
  Trophy,
  type LucideIcon,
} from 'lucide-react'
import { t } from '@/i18n/core'

export const GOALS = (): Record<string, { title: string; hint: string; icon: LucideIcon }> => ({
  first_ride: {
    title: t('Первая поездка'),
    hint: t('Завершите первую поездку'),
    icon: Flag,
  },
  regular_passenger: {
    title: t('Частый пассажир'),
    hint: t('5 поездок'),
    icon: Repeat,
  },
  loyal_passenger: {
    title: t('Верный пассажир'),
    hint: t('25 поездок'),
    icon: Heart,
  },
  feedback: {
    title: t('Обратная связь'),
    hint: t('Оцените 3 поездки'),
    icon: MessageCircle,
  },
  explorer: {
    title: t('Исследователь'),
    hint: t('Проедьте 50 км'),
    icon: Compass,
  },
  night_owl: {
    title: t('Ночная птица'),
    hint: t('Поездка с 22:00 до 5:00'),
    icon: Moon,
  },
  premium: {
    title: t('Бизнес-класс'),
    hint: t('Поездка в «Комфорт+» или «Бизнес»'),
    icon: Gem,
  },
  kaspi_fan: {
    title: t('Kaspi-пассажир'),
    hint: t('3 поездки с оплатой Kaspi'),
    icon: CreditCard,
  },
  bonus_saver: {
    title: t('Экономист'),
    hint: t('Оплатите поездку бонусами'),
    icon: PiggyBank,
  },
  streak_keeper: {
    title: t('Без пропусков'),
    hint: t('4 недели подряд с поездками'),
    icon: Flame,
  },
  first_order: {
    title: t('Первый заказ'),
    hint: t('Выполните первый заказ'),
    icon: Flag,
  },
  experienced_driver: {
    title: t('Опытный водитель'),
    hint: t('10 поездок'),
    icon: Car,
  },
  road_master: {
    title: t('Мастер дорог'),
    hint: t('50 поездок'),
    icon: Trophy,
  },
  high_rating: {
    title: t('Высокая оценка'),
    hint: t('Средняя 4,8 из 5 оценок'),
    icon: Star,
  },
  marathon: { title: t('Марафонец'), hint: t('Проедьте 300 км'), icon: Route },
  night_shift: {
    title: t('Ночная смена'),
    hint: t('5 ночных поездок'),
    icon: Moon,
  },
  five_stars: {
    title: t('Пять звёзд'),
    hint: t('10 оценок «5»'),
    icon: Sparkles,
  },
})

export function goalTitle(code: string): string {
  return GOALS()[code]?.title ?? code
}
