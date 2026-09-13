import { useEffect, useState } from 'react'
import { api } from '../api'
import { MUTED, INK_TEXT, SLATE_400, SLATE_200, DEEP_TEAL } from '../styles'

// A full year, consistent with the brand-position matrix - steadier,
// more representative numbers than a shorter rolling window.
const DAYS = 365

// The value-prop rows, top to bottom - reusing the existing, already
// classified message-attribute taxonomy exactly as-is (no new
// classification work): the customer-facing value props that don't map to
// an existing attribute (Widest Selection, Free Maintenance) aren't
// included here rather than shown as a guess.
const VALUE_PROPS = [
  'Safety & Protection',
  'Trust & Reliability',
  'Price & Value',
  'Convenience & Speed',
  'Expertise & Professionalism',
  'Local & Community',
  'Quality & Craftsmanship',
]

const W = 760, ROW_H = 46, PAD_TOP = 16, PAD_BOTTOM = 34
const LABEL_W = 220, PLOT_R_PAD = 60
const HEIGHT = PAD_TOP + PAD_BOTTOM + ROW_H * (VALUE_PROPS.length - 1)

// Sum raw attribute counts across every company in a group - the real
// share of everything that group has actually posted in the window, same
// denominator convention used everywhere else in this app (full
// classified total, not renormalized to just the shown attributes).
function aggregate(rows) {
  const totals = {}
  let classifiedTotal = 0
  for (const r of rows) {
    for (const [k, v] of Object.entries(r.by_attribute || {})) {
      totals[k] = (totals[k] || 0) + v
      classifiedTotal += v
    }
  }
  return { totals, classifiedTotal }
}

const selectStyle = {
  fontSize: 11, fontWeight: 600, padding: '5px 10px', borderRadius: 7, border: `1px solid ${SLATE_200}`,
  color: DEEP_TEAL, background: '#FFFFFF', fontFamily: 'Poppins, sans-serif', cursor: 'pointer',
}

export default function ValueMap({ categories }) {
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
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Value map: what each side actually leads with</div>
          <div style={{ fontSize: 11, color: MUTED, maxWidth: 620 }}>
            For each value proposition, the real share of a group's classified output (past year) that leans on it - how much a
            brand communicates something stands in for how much it leads with that value.
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
        <ValueMapPlot ours={ours.rows} compared={compared.rows} compareCategory={effectiveCompareCategory} />
      )}
    </div>
  )
}

function ValueMapPlot({ ours, compared, compareCategory }) {
  const a = aggregate(ours)
  const b = aggregate(compared)
  if (!a.classifiedTotal && !b.classifiedTotal) {
    return <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic', padding: '30px 0' }}>Not enough classified data for either group yet.</div>
  }

  const pct = (agg, attr) => (agg.classifiedTotal ? (agg.totals[attr] || 0) / agg.classifiedTotal * 100 : 0)
  const values = VALUE_PROPS.flatMap((attr) => [pct(a, attr), pct(b, attr)])
  const maxVal = Math.max(...values, 5)

  const plotW = W - LABEL_W - PLOT_R_PAD
  const x = (v) => LABEL_W + (v / maxVal) * plotW
  const y = (i) => PAD_TOP + i * ROW_H

  const linePoints = (agg) => VALUE_PROPS.map((attr, i) => `${x(pct(agg, attr))},${y(i)}`).join(' ')

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 10, fontSize: 10, color: MUTED }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 16, height: 2, background: DEEP_TEAL, display: 'inline-block' }} /> Mavis family
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 16, height: 2, background: SLATE_400, display: 'inline-block' }} /> {compareCategory}
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${HEIGHT}`} style={{ width: '100%', height: 'auto', display: 'block', maxWidth: W }}>
        {VALUE_PROPS.map((attr, i) => (
          <g key={attr}>
            <line x1={LABEL_W} y1={y(i)} x2={W - PLOT_R_PAD + 14} y2={y(i)} stroke={SLATE_200} strokeWidth={1} />
            <text x={LABEL_W - 12} y={y(i) + 4} fontSize="11" fill={INK_TEXT} textAnchor="end" fontWeight={600}>{attr}</text>
          </g>
        ))}

        <polyline points={linePoints(b)} fill="none" stroke={SLATE_400} strokeWidth={2} />
        <polyline points={linePoints(a)} fill="none" stroke={DEEP_TEAL} strokeWidth={2.5} />

        {VALUE_PROPS.map((attr, i) => (
          <g key={`pts-${attr}`}>
            <circle cx={x(pct(b, attr))} cy={y(i)} r={4.5} fill={SLATE_400} stroke="#FFFFFF" strokeWidth={1.5}>
              <title>{`${compareCategory} — ${attr}: ${pct(b, attr).toFixed(1)}% of classified output`}</title>
            </circle>
            <circle cx={x(pct(a, attr))} cy={y(i)} r={4.5} fill={DEEP_TEAL} stroke="#FFFFFF" strokeWidth={1.5}>
              <title>{`Mavis family — ${attr}: ${pct(a, attr).toFixed(1)}% of classified output`}</title>
            </circle>
          </g>
        ))}

        <line x1={LABEL_W} y1={HEIGHT - PAD_BOTTOM + 14} x2={W - PLOT_R_PAD + 14} y2={HEIGHT - PAD_BOTTOM + 14} stroke={SLATE_200} strokeWidth={1} />
        <text x={LABEL_W} y={HEIGHT - 8} fontSize="9.5" fill={MUTED}>0%</text>
        <text x={W - PLOT_R_PAD + 14} y={HEIGHT - 8} fontSize="9.5" fill={MUTED} textAnchor="end">{maxVal.toFixed(0)}%</text>
      </svg>
      <div style={{ textAlign: 'center', marginTop: 2, fontSize: 10.5, fontWeight: 700, color: INK_TEXT, letterSpacing: '.03em' }}>
        SHARE OF CLASSIFIED OUTPUT LEANING ON THIS VALUE PROP (PAST YEAR) →
      </div>
    </div>
  )
}
