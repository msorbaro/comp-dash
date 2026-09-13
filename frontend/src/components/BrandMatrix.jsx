import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtNum, MUTED, INK_TEXT, SLATE_600, SLATE_400, SLATE_200, DEEP_TEAL, SURFACE } from '../styles'

// A full year, not a rolling 90 days - cadence and message mix are steadier
// and more representative measured over a brand's last 12 months than a
// shorter window that can be skewed by one campaign or a quiet quarter.
const DAYS = 365
const HEIGHT = 420
// Keep markers off the hard edges of the plot so a brand at the extreme of
// either axis doesn't get clipped or sit flush against the border.
const PAD = 8

function median(nums) {
  if (!nums.length) return 0
  const sorted = [...nums].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function valueSharePct(row) {
  const classified = Object.values(row.by_attribute || {}).reduce((a, b) => a + b, 0)
  if (!classified) return 0
  return (row.by_attribute['Price & Value'] / classified) * 100
}

// The full story behind one brand's dot: not just "62% value-led", but
// what the OTHER 38% actually is (the single biggest non-price attribute),
// plus the complete attribute breakdown underneath - shown as a native
// tooltip (multi-line via \n, no library needed).
function breakdownTooltip(row) {
  const attrs = row.by_attribute || {}
  const total = Object.values(attrs).reduce((a, b) => a + b, 0)
  const freq = (row.total / (DAYS / 7)).toFixed(1)
  const header = `${row.company} — ${freq} posts/week (past year)`
  if (!total) return `${header}\nNot enough classified content yet.`

  const sorted = Object.entries(attrs).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1])
  const valueCount = attrs['Price & Value'] || 0
  const valuePct = Math.round((valueCount / total) * 100)
  const brandPct = 100 - valuePct
  const topOther = sorted.find(([k]) => k !== 'Price & Value')
  const summary = topOther
    ? `${valuePct}% value-led (Price & Value). The remaining ${brandPct}% is brand-led, mostly ${topOther[0]} (${Math.round((topOther[1] / total) * 100)}%).`
    : `${valuePct}% value-led (Price & Value). ${brandPct}% brand-led.`

  const lines = sorted.map(([k, v]) => `  ${Math.round((v / total) * 100)}%  ${k}`)
  return `${header}\n${summary}\n\nFull breakdown (% of classified output):\n${lines.join('\n')}`
}

// Fixed-size logo marker with a colored ring identifying the group (ours vs
// the comparison category), and a graceful initial-letter fallback if the
// favicon fails to load or was never available.
function Marker({ row, group, xPct, yPct }) {
  const [broken, setBroken] = useState(false)
  const ringColor = group === 'ours' ? DEEP_TEAL : SLATE_400
  const showFallback = !row.logo_url || broken
  return (
    <div
      title={breakdownTooltip(row)}
      style={{
        position: 'absolute', left: `${xPct}%`, top: `${yPct}%`, transform: 'translate(-50%, -50%)',
        width: 32, height: 32, borderRadius: '50%', background: SURFACE,
        border: `2px solid ${ringColor}`, boxShadow: '0 1px 3px rgba(15,20,24,.12)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', cursor: 'default',
      }}
    >
      {showFallback ? (
        <div style={{
          width: '100%', height: '100%', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(135deg,#0F7A84,#22B8C4)', color: '#FFFFFF', fontSize: 12, fontWeight: 700,
        }}>
          {row.company[0]}
        </div>
      ) : (
        <img src={row.logo_url} alt="" onError={() => setBroken(true)} style={{ width: 20, height: 20, objectFit: 'contain' }} />
      )}
    </div>
  )
}

// Greedy declutter in percentage space: several brands commonly land at a
// very similar posting cadence and value-share (e.g. a cluster of brands
// that never lead with price), so raw positions alone frequently produce
// overlapping logos. Nudges a point's vertical position in small steps,
// alternating up/down, until it clears nearby already-placed points.
function declutter(points) {
  const THRESH_X = 6, THRESH_Y = 11, STEP = 10
  const placed = []
  const ordered = [...points].sort((a, b) => a.xPct - b.xPct)
  return ordered.map((p) => {
    let y = p.yPct
    let tries = 0
    while (tries < 8 && placed.some((q) => Math.abs(q.x - p.xPct) < THRESH_X && Math.abs(q.y - y) < THRESH_Y)) {
      const dir = tries % 2 === 0 ? 1 : -1
      y = p.yPct + dir * STEP * Math.ceil((tries + 1) / 2)
      tries++
    }
    y = Math.max(PAD, Math.min(100 - PAD, y))
    placed.push({ x: p.xPct, y })
    return { ...p, yPct: y }
  })
}

const selectStyle = {
  fontSize: 11, fontWeight: 600, padding: '5px 10px', borderRadius: 7, border: `1px solid ${SLATE_200}`,
  color: DEEP_TEAL, background: '#FFFFFF', fontFamily: 'Poppins, sans-serif', cursor: 'pointer',
}

function QuadrantLabel({ corner, children }) {
  const pos = {
    tl: { top: 10, left: 10, textAlign: 'left' }, tr: { top: 10, right: 10, textAlign: 'right' },
    bl: { bottom: 10, left: 10, textAlign: 'left' }, br: { bottom: 10, right: 10, textAlign: 'right' },
  }[corner]
  return (
    <div style={{
      position: 'absolute', ...pos, maxWidth: 190, fontSize: 10.5, lineHeight: 1.35, letterSpacing: '.01em',
      color: SLATE_600, fontWeight: 600, pointerEvents: 'none', background: 'rgba(255,255,255,.75)', padding: '3px 6px', borderRadius: 5,
    }}>
      {children}
    </div>
  )
}

// Where each brand sits on posting frequency (x) against how value-led vs.
// brand-led its messaging is (y) - "value-led" meaning a majority of its
// classified message attributes are Price & Value; "brand-led" meaning the
// majority is everything else (Trust, Quality, Emotional, etc). The
// comparison side is whichever category is picked below.
export default function BrandMatrix({ categories }) {
  const [compareCategory, setCompareCategory] = useState('Automotive Full Service')
  const [ours, setOurs] = useState(null)
  const [compared, setCompared] = useState(null)
  const [error, setError] = useState(null)

  const compareOptions = categories.filter((c) => c !== 'Our Brands')
  const effectiveCompareCategory = compareOptions.includes(compareCategory) ? compareCategory : (compareOptions[0] || '')

  const load = () => {
    setError(null)
    Promise.all([
      api.landscapeVolume('Our Brands', DAYS),
      effectiveCompareCategory ? api.landscapeVolume(effectiveCompareCategory, DAYS) : Promise.resolve(null),
    ]).then(([a, b]) => { setOurs(a); setCompared(b) }).catch((e) => setError(e.message))
  }
  useEffect(load, [effectiveCompareCategory])

  return (
    <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 4 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Where each brand plays: frequency vs. value-led messaging</div>
          <div style={{ fontSize: 11, color: MUTED, maxWidth: 620 }}>
            X is how often a brand posts (posts/week, over the past year). Y is whether its message mix leans Price &amp; Value
            ("value-led", top) or everything else - Trust, Quality, Emotional, etc ("brand-led", bottom). Hover a logo for the
            full attribute breakdown behind it.
          </div>
        </div>
        <div>
          <div style={{ fontSize: 9, letterSpacing: '.1em', color: MUTED, fontWeight: 600, marginBottom: 6 }}>COMPARE AGAINST</div>
          <select value={effectiveCompareCategory} onChange={(e) => setCompareCategory(e.target.value)} style={selectStyle}>
            {compareOptions.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {error ? (
        <div style={{ padding: '30px 0', color: MUTED }}>
          Couldn't load this section ({error}).{' '}
          <span onClick={load} style={{ textDecoration: 'underline', cursor: 'pointer' }}>Try again</span>
        </div>
      ) : !ours || !compared ? (
        <div style={{ padding: '30px 0', color: MUTED }}>Loading…</div>
      ) : (
        <BrandMatrixPlot ours={ours.rows} compared={compared.rows} compareCategory={effectiveCompareCategory} />
      )}
    </div>
  )
}

function BrandMatrixPlot({ ours, compared, compareCategory }) {
  const all = [
    ...ours.map((r) => ({ row: r, group: 'ours' })),
    ...compared.map((r) => ({ row: r, group: 'compared' })),
  ].filter((p) => p.row.total > 0)

  if (!all.length) return <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic', padding: '30px 0' }}>Not enough data for either group yet.</div>

  const freqs = all.map((p) => p.row.total / (DAYS / 7))
  const maxFreq = Math.max(...freqs, 1)
  const medianFreq = median(freqs)

  const raw = all.map((p) => {
    const freq = p.row.total / (DAYS / 7)
    const value = valueSharePct(p.row)
    return {
      company: p.row.company, group: p.group, row: p.row,
      xPct: PAD + (freq / maxFreq) * (100 - 2 * PAD),
      yPct: PAD + (1 - value / 100) * (100 - 2 * PAD),
    }
  })
  const points = declutter(raw)
  const medianXPct = PAD + (medianFreq / maxFreq) * (100 - 2 * PAD)

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 12, fontSize: 10, color: MUTED }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${DEEP_TEAL}`, display: 'inline-block' }} /> Mavis family
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${SLATE_400}`, display: 'inline-block' }} /> {compareCategory}
        </span>
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        {/* Y-axis title, running alongside the plot */}
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'center', width: 20, padding: '4px 0' }}>
          <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', fontSize: 10.5, fontWeight: 700, color: INK_TEXT, letterSpacing: '.03em' }}>
            ↑ VALUE-LED (Price &amp; Value)
          </div>
          <div style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)', fontSize: 10.5, fontWeight: 700, color: INK_TEXT, letterSpacing: '.03em' }}>
            BRAND-LED (Trust, Quality, Emotional, etc) ↓
          </div>
        </div>

        <div style={{ flex: 1 }}>
          <div style={{ position: 'relative', width: '100%', height: HEIGHT, background: '#FBFCFD', border: `1px solid ${SLATE_200}`, borderRadius: 10 }}>
            <div style={{ position: 'absolute', left: `${medianXPct}%`, top: 0, bottom: 0, width: 1, background: SLATE_200 }} />
            <div style={{ position: 'absolute', left: 0, right: 0, top: '50%', height: 1, background: SLATE_200 }} />

            <QuadrantLabel corner="tr">Posts often &amp; leads with price/value</QuadrantLabel>
            <QuadrantLabel corner="tl">Posts rarely, but leads with price/value</QuadrantLabel>
            <QuadrantLabel corner="br">Posts often &amp; leads with brand/trust</QuadrantLabel>
            <QuadrantLabel corner="bl">Posts rarely &amp; leads with brand/trust</QuadrantLabel>

            {points.map((p) => (
              <Marker key={`${p.group}-${p.company}`} row={p.row} group={p.group} xPct={p.xPct} yPct={p.yPct} />
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, fontSize: 9.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>
            <span>0 posts/wk</span>
            <span>{fmtNum(maxFreq)} posts/wk</span>
          </div>
          <div style={{ textAlign: 'center', marginTop: 4, fontSize: 10.5, fontWeight: 700, color: INK_TEXT, letterSpacing: '.03em' }}>
            POSTING FREQUENCY (posts/week, past year) →
          </div>
        </div>
      </div>
    </div>
  )
}
