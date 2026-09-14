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

// Fixed hue per message attribute, applied everywhere this dimension is
// charted - never re-derived or cycled per view, so the same attribute
// always reads as the same color across the whole app.
export const ATTRIBUTE_COLORS = {
  'Safety & Protection': '#4E79A7',
  'Trust & Reliability': '#59A14F',
  'Price & Value': '#F28E2B',
  'Convenience & Speed': '#76B7B2',
  'Expertise & Professionalism': '#B07AA1',
  'Local & Community': '#9C755F',
  'Quality & Craftsmanship': '#E15759',
  'Emotional & Lifestyle': '#FF9DA7',
  'Social Proof & Reputation': '#EDC948',
  'None Clear / Other': '#C7CDD4',
}
export const ATTRIBUTE_ORDER = Object.keys(ATTRIBUTE_COLORS)

// Short labels for the same 10 attributes, for tight chart axes/legends
// where the full name ("Emotional & Lifestyle") doesn't fit.
export const ATTRIBUTE_SHORT = {
  'Safety & Protection': 'Safety', 'Trust & Reliability': 'Trust', 'Price & Value': 'Price',
  'Convenience & Speed': 'Speed', 'Expertise & Professionalism': 'Expertise',
  'Local & Community': 'Local', 'Quality & Craftsmanship': 'Quality',
  'Emotional & Lifestyle': 'Emotion', 'Social Proof & Reputation': 'Social proof',
  'None Clear / Other': 'Unclear',
}

function _hexByte(n) {
  return Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, '0')
}
function _lerpHex(a, b, t) {
  const parse = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16))
  const [ar, ag, ab] = parse(a)
  const [br, bg, bb] = parse(b)
  return `#${_hexByte(ar + (br - ar) * t)}${_hexByte(ag + (bg - ag) * t)}${_hexByte(ab + (bb - ab) * t)}`
}
// Sequential heat ramp for the territory heatmap (matrix 01) - one hue,
// light to dark, interpolated between the app's own TEAL_WASH and
// DEEP_TEAL tokens rather than a separate foreign color scheme. `pct` is
// a 0-100 share; values above HEAT_MAX read as fully saturated.
const HEAT_MAX = 60
export function heatColor(pct) {
  const t = Math.max(0, Math.min(1, (pct || 0) / HEAT_MAX))
  return _lerpHex(TEAL_WASH, DEEP_TEAL, t)
}
export function heatTextColor(pct) {
  return (pct || 0) / HEAT_MAX > 0.55 ? '#FFFFFF' : INK_TEXT
}

// Mirrors backend/signal_data.py's CHANNELS list (id/name/paid) - kept as a
// small duplicated constant here the same way STAGES already is, since the
// channel-breakdown API responses are keyed by these raw ids, not names.
export const CHANNELS = [
  { id: 'search', name: 'Paid Search', paid: true },
  { id: 'meta_ads', name: 'IG / FB Ads', paid: true },
  { id: 'ig_organic', name: 'Instagram Organic', paid: false },
  { id: 'tiktok', name: 'TikTok', paid: false },
  { id: 'youtube', name: 'YouTube', paid: false },
  { id: 'x', name: 'X / Twitter', paid: false },
  { id: 'homepage', name: 'Homepage', paid: false },
]
export const CHANNEL_ORDER = CHANNELS.map((c) => c.id)
export const CHANNEL_NAME = Object.fromEntries(CHANNELS.map((c) => [c.id, c.name]))
// Warm tones for paid channels, cool/distinct tones for owned ones - a
// secondary encoding of the paid/owned split that's already used elsewhere
// in the app, while still letting each channel read as its own color.
export const CHANNEL_COLORS = {
  search: '#D97706',
  meta_ads: '#B45309',
  ig_organic: '#22B8C4',
  tiktok: '#7C3AED',
  youtube: '#2563EB',
  x: '#16A34A',
  homepage: '#64748B',
}

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

// Real classified message-attribute counts -> displayable rows, sorted by
// prominence, excluding the catch-all bucket. Works for both the one-sided
// case (Category page: just `breakdown`) and the two-sided comparison
// (Landscape page: `breakdown` = ours, `otherBreakdown` = the rest of the
// market) - pass otherBreakdown only when you have a comparison to show.
export function attributeRows(breakdown, otherBreakdown = null, limit = 5) {
  if (!breakdown) return []
  const ourTotal = breakdown.total || 0
  const otherTotal = otherBreakdown?.total || 0
  const attrs = Object.keys(breakdown.counts || {}).filter((a) => a !== 'None Clear / Other')
  const rows = attrs.map((attribute) => {
    const ourCount = breakdown.counts[attribute] || 0
    const otherCount = otherBreakdown?.counts?.[attribute] || 0
    return {
      attribute,
      ourCount, ourTotal, ourPct: ourTotal ? Math.round((ourCount / ourTotal) * 100) : 0,
      otherCount, otherTotal, otherPct: otherTotal ? Math.round((otherCount / otherTotal) * 100) : 0,
    }
  })
  const sortKey = otherBreakdown ? (r) => r.otherPct : (r) => r.ourPct
  return rows.sort((a, b) => sortKey(b) - sortKey(a)).filter((r) => r.ourCount > 0 || r.otherCount > 0).slice(0, limit)
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

// Heights are generous and images render with object-fit:contain (never
// cropped) since ad/homepage creative comes in very different aspect ratios
// (square posts, portrait story ads, tall homepage screenshots, landscape
// video thumbnails) - a fixed crop would cut off real content.
export const MEDIA_HEIGHT = { vertical: 320, wide: 160, search: 260, square: 190 }

export const cardBase = { background: SURFACE, border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px' }
export const inkPanel = { background: INK, borderRadius: 13, padding: '24px 26px', color: '#FFFFFF' }

// Shown ALWAYS (not just on hover - a tooltip alone wasn't being noticed) as
// a caption directly under each top-level brand stat, so "69" or "4/7" is
// never an unexplained number.
export const METRIC_DEFINITIONS = {
  trackedOutput: '90-day total across all channels, shown as a monthly rate (÷3).',
  activeChannels: 'Channels averaging at least 5 posts/ads per month over the last 90 days, out of 7 tracked. Homepage always counts as active (checked weekly regardless of change).',
}

export function engagementExplanation(channelId) {
  return {
    ig_organic: 'Average likes per post.',
    tiktok: 'Average views per video.',
    youtube: 'Average views per video.',
    x: 'Average likes + retweets per post.',
    meta_ads: 'Not tracked — Meta’s Ads Library does not expose public engagement numbers for ads.',
    search: 'Not tracked — Google’s Ads Transparency Center does not expose engagement numbers.',
    homepage: 'Not applicable — a homepage snapshot has no engagement metric.',
  }[channelId] || 'Not tracked for this channel.'
}

// Short version for the narrow "Avg. engagement" column itself.
export function engagementUnitLabel(channelId) {
  return {
    ig_organic: 'avg likes / post', tiktok: 'avg views / video', youtube: 'avg views / video',
    x: 'avg likes+RTs / post', meta_ads: 'not tracked', search: 'not tracked', homepage: 'n/a',
  }[channelId] || 'not tracked'
}
