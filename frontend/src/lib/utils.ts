import { createCn } from 'cn/config'

/** Figma text styles declared in index.css (`--text-*`), so merging keeps them apart from text colours. */
const FIGMA_TEXT_STYLES = ['display', 'title', 'headline', 'body-medium', 'body', 'callout', 'caption', 'label']

export const cn = createCn({
  extend: {
    classGroups: {
      'font-size': [{ text: FIGMA_TEXT_STYLES }],
      shadow: [{ shadow: ['card', 'sheet'] }],
    },
  },
})
