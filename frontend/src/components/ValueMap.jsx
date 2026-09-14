import { useEffect, useState } from 'react'
import { api } from '../api'
import { Shimmer } from './Widgets'
import { MUTED, INK_TEXT, SLATE_200, DEEP_TEAL } from '../styles'

// A full year, consistent with the brand-position matrix - steadier,
// more representative numbers than a shorter rolling window.
const DAYS = 365

// The value-prop rows, top to bottom - reusing the existing, already
// classified message-attribute taxonomy exactly as-is (no new
// classification work).
const VALUE_PROPS = [
  'Safety & Protection',
  'Trust & Reliability',
  'Price & Value',
  'Convenience & Speed',
  'Expertise & Professionalism',
  'Local & Community',
  'Quality & Craftsmanship',
]

const ROW_H = 42, PAD_TOP = 14, PAD_BOTTOM = 46
const HEIGHT = PAD_TOP + PAD_BOTTOM + ROW_H * (VALUE_PROPS.length - 1)
const LABEL_W = 190, CHART_W = 260, RIGHT_MARGIN = 20
const W = LABEL_W + CHART_W + RIGHT_MARGIN

// One color per line, reused by position (not tied to any other chart's
// meaning) - enough distinct hues for the largest group (Our Brands, 9).
const BRAND_COLORS = [
  '#0B4F55', '#D97706', '#7C3AED', '#DC2626', '#2563EB', '#16A34A',
  '#DB2777', '#0EA5E9', '#CA8A04', '#059669', '#9333EA', '#EA580C',
]

// A distinct dash rhythm per line (cycled by position, same as color) -
// two lines landing on the exact same scores every row is common here
// (the 1-5 rank is coarse), and a plain solid stroke makes one line
// completely hide the other. Different dash lengths per line mean the
// gaps don't line up, so both colors stay visible where they overlap.
const DASH_PATTERNS = ['none', '6,3', '2,3', '8,2,2,2', '1,3', '10,3,2,3']

function pctForCompany(row, attr) {
  const total = Object.values(row.by_attribute || {}).reduce((a, b) => a + b, 0)
  if (!total) return 0
  return ((row.by_attribute[attr] || 0) / total) * 100
}

// Even (quantile) buckets: for one value prop, sort every company's real %
// score, split into 5 equal-ish groups, score = 1 (bottom group) to 5 (top
// group). Raw % shares are usually small (rarely above 30-40% for any one
// attribute), so a fixed 0-100 scale would crowd almost everyone into the
// low end - ranking against the actual observed spread instead means the
// full 1-5 scale is always meaningfully used.
function quantileScores(items) {
  const sorted = [...items].sort((a, b) => a.value - b.value)
  const n = sorted.length
  const scores = {}
  sorted.forEach((item, i) => {
    scores[item.key] = Math.min(4, Math.floor((i * 5) / n)) + 1
  })
  return scores
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
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Value map: what each brand actually leads with</div>
          <div style={{ fontSize: 11, color: MUTED, maxWidth: 620 }}>
            Each line is one brand's real message mix (past year) across the same 7 value props. Score is a 1-5 rank against
            every brand shown here, not a raw percentage - how much a brand communicates something stands in for how much it
            leads with that value.
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
        <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginTop: 18 }}>
          <Shimmer width="100%" height={HEIGHT} radius={10} style={{ flex: '1 1 380px', minWidth: 320 }} />
          <Shimmer width="100%" height={HEIGHT} radius={10} style={{ flex: '1 1 380px', minWidth: 320 }} />
        </div>
      ) : (
        <ValueMapPlots ours={ours.rows} compared={compared.rows} compareCategory={effectiveCompareCategory} />
      )}
    </div>
  )
}

function ValueMapPlots({ ours, compared, compareCategory }) {
  const oursActive = ours.filter((r) => r.total > 0)
  const comparedActive = compared.filter((r) => r.total > 0)
  const [hidden, setHidden] = useState(() => new Set())
  const toggleCompany = (name) => {
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  if (!oursActive.length && !comparedActive.length) {
    return <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic', padding: '30px 0' }}>Not enough classified data for either group yet.</div>
  }

  // Pooled across BOTH groups per row, so a "3" means the same thing on
  // both charts - the two sides stay directly comparable. Computed from
  // every active company regardless of which are hidden, so toggling
  // visibility never shifts the scale for the ones still shown.
  const scoresByAttr = {}
  for (const attr of VALUE_PROPS) {
    const items = [...oursActive, ...comparedActive].map((r) => ({ key: r.company, value: pctForCompany(r, attr) }))
    scoresByAttr[attr] = quantileScores(items)
  }

  return (
    <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap' }}>
      <ValueMapChart title="Mavis family of brands" rows={oursActive} scoresByAttr={scoresByAttr} hidden={hidden} onToggle={toggleCompany} showLabels />
      <ValueMapChart title={compareCategory} rows={comparedActive} scoresByAttr={scoresByAttr} hidden={hidden} onToggle={toggleCompany} />
    </div>
  )
}

function ValueMapChart({ title, rows, scoresByAttr, hidden, onToggle, showLabels = false }) {
  const x = (score) => LABEL_W + ((score - 1) / 4) * CHART_W
  const y = (i) => PAD_TOP + i * ROW_H
  const visibleRows = rows.filter((r) => !hidden.has(r.company))

  return (
    <div style={{ flex: '1 1 380px', minWidth: 320 }}>
      <div style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 8 }}>{title}</div>
      {!rows.length ? (
        <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>No data yet.</div>
      ) : (
        <>
          <svg viewBox={`0 0 ${W} ${HEIGHT}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
            {VALUE_PROPS.map((attr, i) => (
              <g key={attr}>
                <line x1={LABEL_W} y1={y(i)} x2={W - RIGHT_MARGIN} y2={y(i)} stroke={SLATE_200} strokeWidth={1} />
                {showLabels && (
                  <text x={LABEL_W - 12} y={y(i) + 4} fontSize="10.5" fill={INK_TEXT} textAnchor="end" fontWeight={600}>{attr}</text>
                )}
              </g>
            ))}

            {visibleRows.map((r) => {
              const ri = rows.indexOf(r)
              const color = BRAND_COLORS[ri % BRAND_COLORS.length]
              const dash = DASH_PATTERNS[ri % DASH_PATTERNS.length]
              const pts = VALUE_PROPS.map((attr, i) => `${x(scoresByAttr[attr][r.company])},${y(i)}`).join(' ')
              return (
                <g key={r.company}>
                  <polyline points={pts} fill="none" stroke={color} strokeWidth={2} strokeDasharray={dash} opacity={0.9} />
                  {VALUE_PROPS.map((attr, i) => (
                    <circle key={attr} cx={x(scoresByAttr[attr][r.company])} cy={y(i)} r={4} fill={color} stroke="#FFFFFF" strokeWidth={1.2}>
                      <title>{`${r.company} — ${attr}: ${scoresByAttr[attr][r.company]}/5 (${pctForCompany(r, attr).toFixed(1)}% of classified output)`}</title>
                    </circle>
                  ))}
                </g>
              )
            })}

            {[1, 2, 3, 4, 5].map((s) => (
              <text key={s} x={x(s)} y={HEIGHT - PAD_BOTTOM + 20} fontSize="10" fill={MUTED} textAnchor="middle">{s}</text>
            ))}
            <text x={LABEL_W} y={HEIGHT - 6} fontSize="9" fill={MUTED} letterSpacing=".05em">LOW</text>
            <text x={W - RIGHT_MARGIN} y={HEIGHT - 6} fontSize="9" fill={MUTED} letterSpacing=".05em" textAnchor="end">HIGH</text>
          </svg>
          <div style={{ fontSize: 9, color: MUTED, marginTop: 8, marginBottom: 2 }}>Click a company to show/hide it:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 10px', fontSize: 9.5 }}>
            {rows.map((r, ri) => {
              const isHidden = hidden.has(r.company)
              return (
                <span
                  key={r.company}
                  onClick={() => onToggle(r.company)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, cursor: 'pointer', color: isHidden ? '#B7C0CA' : MUTED, textDecoration: isHidden ? 'line-through' : 'none' }}
                >
                  <span style={{
                    width: 8, height: 8, borderRadius: '50%', display: 'inline-block', flex: 'none',
                    background: isHidden ? '#E2E8F0' : BRAND_COLORS[ri % BRAND_COLORS.length],
                  }} />
                  {r.company}
                </span>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
