// Design tokens copied verbatim from `new designs/Design System.dc.html`.
export const INK = '#141A21'
export const INK_80 = '#1F2831'
export const DEEP_TEAL = '#0B4F55'
export const TEAL = '#22B8C4'
export const TEAL_700 = '#0F7A84'
export const TEAL_WASH = '#EAF6F8'
export const AMBER = '#D97706'
export const ROSE = '#E11D48'
export const GREEN = '#16A34A'
export const SLATE_600 = '#475569'
export const SLATE_400 = '#94A3B8'
export const SLATE_200 = '#E2E8F0'
export const CANVAS = '#F6F8FA'
export const SURFACE = '#FFFFFF'
export const TRACK = '#EEF2F6'
export const ROW_LINE = '#F1F5F9'
export const INK_TEXT = '#1A1F26'
export const MUTED = '#6B7885'
export const MONO = 'ui-monospace,Menlo,monospace'

export const STAGES = [
  { id: 'see', name: 'See', color: TEAL, desc: 'Broad reach to people who may or may not be in market. Goal is awareness and one memorable message.' },
  { id: 'think', name: 'Think', color: DEEP_TEAL, desc: 'People who have shown interest but are not ready. Goal is helping them choose.' },
  { id: 'do', name: 'Do', color: AMBER, desc: 'Active intent. Goal is winning the transaction over every competitor.' },
]

export const COMPETES_LABEL = { direct: 'DIRECT COMPETITOR', adjacent: 'ADJACENT INDUSTRY', 'read-across': 'READ-ACROSS', portfolio: 'OUR PORTFOLIO' }

export function fmtNum(n) {
  if (n === null || n === undefined) return '—'
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 10000) return Math.round(n / 1000) + 'k'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(Math.round(n))
}

export function mixLabel(mix) {
  return `${mix[0]} / ${mix[1]} / ${mix[2]}`
}

export function dominantIdx(mix) {
  return mix.indexOf(Math.max(...mix))
}

export function verdict(mix) {
  const labels = ['See-led · buying attention', 'Think-led · educating shoppers', 'Do-led · pushing conversion']
  return labels[dominantIdx(mix)]
}

export function dominantWord(mix) {
  return ['See-led', 'Think-led', 'Do-led'][dominantIdx(mix)]
}

export function paidChipStyle(paid) {
  return paid
    ? { display: 'inline-block', marginTop: 5, fontSize: 8.5, letterSpacing: '.1em', fontWeight: 600, color: AMBER, background: '#FEF6E7', border: '1px solid #F6E0BC', borderRadius: 4, padding: '2px 5px' }
    : { display: 'inline-block', marginTop: 5, fontSize: 8.5, letterSpacing: '.1em', fontWeight: 600, color: TEAL_700, background: TEAL_WASH, border: '1px solid #CFE9EC', borderRadius: 4, padding: '2px 5px' }
}

export function competesBadgeStyle(kind, onDark) {
  const color = kind === 'direct' ? ROSE : kind === 'portfolio' ? DEEP_TEAL : SLATE_600
  const bg = onDark ? 'rgba(255,255,255,.9)' : kind === 'direct' ? '#FDEEF2' : kind === 'portfolio' ? '#EAF6F8' : '#F1F5F9'
  const border = kind === 'direct' ? '#F7CBD6' : kind === 'portfolio' ? '#CFE9EC' : SLATE_200
  return { display: 'inline-block', fontSize: 8.5, letterSpacing: '.11em', fontWeight: 600, padding: '3px 6px', borderRadius: 4, color, background: bg, border: `1px solid ${border}` }
}

export function trendColor(trend) {
  if (trend === null || trend === undefined) return MUTED
  return trend >= 0 ? GREEN : ROSE
}

export function trendLabel(trend) {
  if (trend === null || trend === undefined) return 'no prior-period data'
  return `${trend >= 0 ? '▲ +' : '▼ '}${trend}% vs prior 90d`
}

export const MEDIA_HEIGHT = { vertical: 118, wide: 84, text: 76, square: 104 }

export const cardBase = { background: SURFACE, border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px' }
export const inkPanel = { background: INK, borderRadius: 13, padding: '24px 26px', color: '#FFFFFF' }
