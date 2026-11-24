const PLATE = /^(\d{3})([A-Z]{2,3})(\d{2})$/

/** «123ABC02», «123 ABC 02» → digits, letters and region; null for other formats. */
export function parseKzPlate(raw: string): { digits: string; letters: string; region: string } | null {
  const match = PLATE.exec(raw.replace(/[\s-]/g, '').toUpperCase())
  if (!match) return null
  const [, digits = '', letters = '', region = ''] = match
  return { digits, letters, region }
}
