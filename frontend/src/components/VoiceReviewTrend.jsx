import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { RowDivider } from './Widgets'
import {
  MUTED, INK_TEXT, SLATE_600, SLATE_200, SLATE_400, DEEP_TEAL, TEAL_700, TEAL_WASH, CANVAS,
  MONO, GREEN, ROSE, ATTRIBUTE_COLORS, fmtNum,
} from '../styles'

// Fixed hue order, reusing the app's own established categorical palette
// (already validated for this design system) rather than inventing a new
// one for a single chart - the catch-all gray in that palette is reserved
// here for the "Competitors" aggregate line below.
const MAVIS_LINE_COLORS = Object.values(ATTRIBUTE_COLORS).slice(0, -1)
const COMPETITOR_COLOR = SLATE_600
// Extra hues for individually-broken-out competitor lines (split mode) -
// cycles independently of the Mavis palette so a Mavis banner and a
// competitor never land on the same color.
const SPLIT_COMPETITOR_COLORS = ['#B45309', '#7C3AED', '#DB2777', '#0891B2', '#65A30D', '#DC2626', '#4F46E5', '#0D9488']

const THEME_LABELS = {
  price_value: 'Price / value', speed_wait_time: 'Speed / wait time', customer_service: 'Customer service',
  technical_quality: 'Technical quality', honesty_trust: 'Honesty / trust', upselling_pressure: 'Upselling / pressure',
  convenience_location: 'Convenience / location', scheduling_ease: 'Scheduling ease', communication: 'Communication',
  cleanliness_facility: 'Cleanliness / facility', warranty_followup: 'Warranty / follow-up',
  product_selection: 'Product selection', other: 'Other',
}

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

function selectStyle() {
  return { fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }
}

// A visually distinct block for each major part of the page, so it's never
// ambiguous where one chart group ends and the next begins - a full-bleed
// background band (not just a thin rule) that reads as "you've entered a
// new section," plus a scope line spelling out exactly which of the
// filters up top actually apply here (the user's own ask: "it's unclear
// what filters apply to which graphs"). The -22px horizontal margin bleeds
// the band to the edges of the parent cardBase panel (Voice.jsx wraps this
// whole page in one with 22px horizontal padding) rather than stopping
// short and looking like a rounded chip.
function Section({ title, scope, children, sectionRef }) {
  return (
    <div ref={sectionRef} style={{ marginTop: 44 }}>
      <div style={{ background: CANVAS, margin: '0 -22px', padding: '18px 22px 16px', borderTop: `1px solid ${SLATE_200}`, borderBottom: `1px solid ${SLATE_200}` }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: INK_TEXT, marginBottom: scope ? 6 : 0 }}>{title}</div>
        {scope && (
          <div style={{ fontSize: 10.5, color: TEAL_700, fontWeight: 600, background: TEAL_WASH, display: 'inline-block', padding: '3px 9px', borderRadius: 12 }}>
            {scope}
          </div>
        )}
      </div>
      <div style={{ paddingTop: 18 }}>{children}</div>
    </div>
  )
}

function fmtMonth(iso) {
  const [y, m] = iso.split('-')
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

function fmtRating(v) {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

function fmtPct(v) {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${Math.round(v * 100)}%`
}

function colorFor(series, mavisIdx, splitIdx) {
  if (series.mavis) return MAVIS_LINE_COLORS[mavisIdx % MAVIS_LINE_COLORS.length]
  if (series.name === 'Competitors') return COMPETITOR_COLOR
  return SPLIT_COMPETITOR_COLORS[splitIdx % SPLIT_COMPETITOR_COLORS.length]
}

// Assigns each series a stable color regardless of which ones are currently
// hidden by the competitor checklist, so toggling visibility never repaints
// the survivors - see the dataviz skill's "color follows the entity" rule.
function useSeriesColors(series) {
  return useMemo(() => {
    let mavisIdx = 0, splitIdx = 0
    const byName = {}
    for (const s of series) {
      byName[s.name] = colorFor(s, mavisIdx, splitIdx)
      if (s.mavis) mavisIdx++
      else if (s.name !== 'Competitors') splitIdx++
    }
    return byName
  }, [series])
}

const CHART_W = 900
const CHART_H = 260
const PAD = { top: 14, right: 16, bottom: 28, left: 34 }

function RatingTrendChart({ series, colorByName }) {
  const [hoverIdx, setHoverIdx] = useState(null)

  const months = useMemo(() => {
    const set = new Set()
    series.forEach((s) => s.points.forEach((p) => set.add(p.month)))
    return [...set].sort()
  }, [series])

  const pointByMonth = useMemo(
    () => series.map((s) => Object.fromEntries(s.points.map((p) => [p.month, p]))),
    [series]
  )

  if (months.length < 2) {
    return <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Not enough months of data yet to chart a trend.</div>
  }

  // The axis range is set from points with a reasonable sample size only -
  // a month with just 1-2 reviews for a thin competitor line can swing to
  // an extreme average (a single 1-star review = a "1.0" point) and would
  // otherwise blow the whole chart's scale out to the floor for no real
  // reason. Falls back to every point if nothing clears the threshold.
  const N_THRESHOLD = 3
  const sampledRatings = series.flatMap((s) => s.points.filter((p) => p.n_reviews >= N_THRESHOLD).map((p) => p.avg_rating).filter((v) => v !== null))
  const allRatings = sampledRatings.length ? sampledRatings : series.flatMap((s) => s.points.map((p) => p.avg_rating).filter((v) => v !== null))
  const yMin = Math.max(1, Math.floor((Math.min(...allRatings) - 0.15) * 10) / 10)
  const yMax = Math.min(5, Math.ceil((Math.max(...allRatings) + 0.15) * 10) / 10)

  const innerW = CHART_W - PAD.left - PAD.right
  const innerH = CHART_H - PAD.top - PAD.bottom
  const xFor = (i) => PAD.left + (months.length === 1 ? innerW / 2 : (i / (months.length - 1)) * innerW)
  const yFor = (v) => PAD.top + innerH - ((Math.min(Math.max(v, yMin), yMax) - yMin) / (yMax - yMin)) * innerH

  const yTicks = []
  for (let v = Math.ceil(yMin * 5) / 5; v <= yMax + 1e-9; v += 0.2) yTicks.push(Math.round(v * 10) / 10)

  const labelEvery = Math.max(1, Math.ceil(months.length / 8))

  const handleMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - rect.left) / rect.width) * CHART_W
    const rel = (x - PAD.left) / innerW
    const idx = Math.round(rel * (months.length - 1))
    setHoverIdx(Math.max(0, Math.min(months.length - 1, idx)))
  }

  const hoverMonth = hoverIdx !== null ? months[hoverIdx] : null

  return (
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${CHART_W} ${CHART_H}`} width="100%" style={{ display: 'block', overflow: 'visible' }}
        onMouseMove={handleMove} onMouseLeave={() => setHoverIdx(null)}
      >
        {yTicks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={CHART_W - PAD.right} y1={yFor(v)} y2={yFor(v)} stroke={SLATE_200} strokeWidth={1} />
            <text x={PAD.left - 8} y={yFor(v) + 3} textAnchor="end" fontSize={9.5} fontFamily={MONO} fill={MUTED}>{v.toFixed(1)}</text>
          </g>
        ))}
        {months.map((m, i) => (
          i % labelEvery === 0 && (
            <text key={m} x={xFor(i)} y={CHART_H - PAD.bottom + 16} textAnchor="middle" fontSize={9.5} fontFamily={MONO} fill={MUTED}>
              {fmtMonth(m)}
            </text>
          )
        ))}

        {hoverIdx !== null && (
          <line x1={xFor(hoverIdx)} x2={xFor(hoverIdx)} y1={PAD.top} y2={CHART_H - PAD.bottom} stroke={SLATE_400} strokeWidth={1} strokeDasharray="2,2" />
        )}

        {series.map((s, si) => {
          const color = colorByName[s.name]
          const pts = months
            .map((m, i) => {
              const p = pointByMonth[si][m]
              // Below N_THRESHOLD reviews, a month's average is one or two
              // reviews' worth of noise (a single 1-star review IS a "1.0"
              // month) - connecting those points with a line across a wide
              // gap read as a wild diagonal spike for a thin series
              // (confirmed live on Tire Kingdom, ~9 reviews total). Treat
              // them as a gap in the LINE (same as a month with no data)
              // but still mark them as a small dot so the data isn't hidden.
              return p && p.avg_rating !== null && p.n_reviews >= N_THRESHOLD ? [xFor(i), yFor(p.avg_rating)] : null
            })
          const sparsePts = months
            .map((m, i) => {
              const p = pointByMonth[si][m]
              return p && p.avg_rating !== null && p.n_reviews > 0 && p.n_reviews < N_THRESHOLD ? [xFor(i), yFor(p.avg_rating)] : null
            })
            .filter(Boolean)
          const segments = []
          let cur = []
          pts.forEach((pt) => {
            if (pt) cur.push(pt)
            else if (cur.length) { segments.push(cur); cur = [] }
          })
          if (cur.length) segments.push(cur)
          return (
            <g key={s.name}>
              {segments.map((seg, i) => (
                <polyline
                  key={i} fill="none" stroke={color} strokeWidth={2}
                  strokeDasharray={s.mavis ? 'none' : '5,3'}
                  points={seg.map(([x, y]) => `${x},${y}`).join(' ')}
                />
              ))}
              {sparsePts.map(([x, y], i) => (
                <circle key={`sparse-${i}`} cx={x} cy={y} r={2} fill="#FFFFFF" stroke={color} strokeWidth={1.5} opacity={0.7} />
              ))}
              {hoverIdx !== null && pointByMonth[si][months[hoverIdx]]?.avg_rating != null && (
                <circle cx={xFor(hoverIdx)} cy={yFor(pointByMonth[si][months[hoverIdx]].avg_rating)} r={3.5} fill={color} stroke="#FFFFFF" strokeWidth={1.5} />
              )}
            </g>
          )
        })}
      </svg>

      {hoverMonth && (
        <div style={{
          position: 'absolute', top: 4, right: 4, background: '#FFFFFF', border: `1px solid ${SLATE_200}`,
          borderRadius: 8, padding: '8px 10px', fontSize: 11, boxShadow: '0 2px 8px rgba(15,20,24,.08)', minWidth: 160, maxHeight: 220, overflowY: 'auto',
        }}>
          <div style={{ fontWeight: 600, marginBottom: 5 }}>{fmtMonth(hoverMonth)}</div>
          {series.map((s, si) => {
            const p = pointByMonth[si][hoverMonth]
            const color = colorByName[s.name]
            return (
              <div key={s.name} style={{ display: 'flex', justifyContent: 'space-between', gap: 10, color: INK_TEXT }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: MUTED }}>
                  <span style={{ width: 8, height: 2, background: color, display: 'inline-block' }} />
                  {s.name}
                </span>
                <span style={{ fontFamily: MONO, fontWeight: 600 }}>
                  {p ? `${fmtRating(p.avg_rating)} (${fmtNum(p.n_reviews)})` : '—'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// A single-month snapshot - each brand's avg rating THAT month, ranked
// best to worst - distinct from the multi-month trend line below it (the
// user's own framing: "the average rating of reviews that month... this is
// different than over time"). Built from the same trend series data
// already fetched for the line chart, no separate query needed.
function MonthlySnapshotChart({ series, month, colorByName }) {
  const rows = series
    .map((s) => ({ name: s.name, mavis: s.mavis, point: s.points.find((p) => p.month === month) }))
    .filter((r) => r.point && r.point.n_reviews > 0 && r.point.avg_rating !== null)
    .sort((a, b) => b.point.avg_rating - a.point.avg_rating)

  if (rows.length === 0) {
    return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No reviews in this scope for this month.</div>
  }
  return (
    <div>
      {rows.map((r) => (
        <div key={r.name} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '4px 0' }}>
          <div style={{ width: 230, flex: 'none', fontSize: 12, fontWeight: r.mavis ? 600 : 400, display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: colorByName[r.name], display: 'inline-block', flex: 'none' }} />
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.name}</span>
            {r.mavis && <span style={{ color: TEAL_700, fontSize: 9, fontFamily: MONO, fontWeight: 600, flex: 'none' }}>MAVIS</span>}
          </div>
          <div style={{ flex: 1, background: SLATE_200, borderRadius: 3, height: 14, position: 'relative', overflow: 'hidden' }}>
            <div style={{ width: `${(r.point.avg_rating / 5) * 100}%`, height: '100%', background: colorByName[r.name], borderRadius: 3 }} />
          </div>
          <div style={{ fontFamily: MONO, fontSize: 11.5, fontWeight: 600, width: 100, flex: 'none', textAlign: 'right' }}>
            {r.point.avg_rating.toFixed(2)}★ <span style={{ color: MUTED, fontWeight: 400 }}>({fmtNum(r.point.n_reviews)})</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function Legend({ series, colorByName }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 10 }}>
      {series.map((s) => {
        const color = colorByName[s.name]
        return (
          <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
            <span style={{
              width: 14, height: 2, display: 'inline-block',
              background: s.mavis ? color : `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 7px)`,
            }} />
            <span style={{ color: s.mavis ? INK_TEXT : MUTED, fontWeight: s.mavis ? 600 : 400 }}>{s.name}</span>
          </div>
        )
      })}
    </div>
  )
}

function CompetitorChecklist({ names, visible, onToggle, onAll, onNone }) {
  if (names.length === 0) return null
  return (
    <div style={{ background: TEAL_WASH, borderRadius: 8, padding: '8px 12px', marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}>
      <span style={{ fontSize: 10, color: MUTED, fontWeight: 600 }}>SHOW:</span>
      <span onClick={onAll} style={{ fontSize: 10.5, color: DEEP_TEAL, cursor: 'pointer', textDecoration: 'underline' }}>all</span>
      <span onClick={onNone} style={{ fontSize: 10.5, color: DEEP_TEAL, cursor: 'pointer', textDecoration: 'underline' }}>none</span>
      {names.map((n) => (
        <label key={n} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, cursor: 'pointer' }}>
          <input type="checkbox" checked={visible.has(n)} onChange={() => onToggle(n)} style={{ margin: 0 }} />
          {n}
        </label>
      ))}
    </div>
  )
}

function SentimentMixChart({ points }) {
  if (points.length === 0) return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No data.</div>
  return (
    <div style={{ display: 'flex', gap: 2, alignItems: 'flex-end', height: 70 }}>
      {points.map((p) => (
        <div key={p.month} title={`${fmtMonth(p.month)} · ${fmtNum(p.n_reviews)} reviews`} style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ flex: p.pct_positive ?? 0, background: GREEN }} />
          <div style={{ flex: p.pct_neutral ?? 0, background: SLATE_400 }} />
          <div style={{ flex: p.pct_negative ?? 0, background: ROSE }} />
        </div>
      ))}
    </div>
  )
}

function YoyBarChart({ points }) {
  if (points.length === 0) return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No data.</div>
  const maxN = Math.max(1, ...points.flatMap((p) => [p.n_this_year, p.n_last_year]))
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height: 130 }}>
      {points.map((p) => (
        <div key={p.month} title={`${fmtMonth(p.month)}: ${p.n_this_year} this year vs ${p.n_last_year} last year (${fmtPct(p.pct_change_n)})`} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}>
          <div style={{ display: 'flex', gap: 2, alignItems: 'flex-end', height: 100, width: '100%', justifyContent: 'center' }}>
            <div style={{ width: '38%', maxWidth: 10, height: `${(p.n_last_year / maxN) * 100}%`, background: SLATE_400, borderRadius: '2px 2px 0 0' }} />
            <div style={{ width: '38%', maxWidth: 10, height: `${(p.n_this_year / maxN) * 100}%`, background: DEEP_TEAL, borderRadius: '2px 2px 0 0' }} />
          </div>
          <div style={{ fontSize: 8.5, color: MUTED, fontFamily: MONO }}>{fmtMonth(p.month)}</div>
        </div>
      ))}
    </div>
  )
}

const YOY_LINE_W = 900
const YOY_LINE_H = 150
const YOY_LINE_PAD = { top: 10, right: 10, bottom: 20, left: 32 }

// Avg rating this year vs. the same month last year, per the user's own
// ask ("avg score this year vs last year") - a companion to YoyBarChart's
// review-count comparison below it, same month axis, same this-year/last-
// year color convention (solid teal / dashed gray).
function YoyRatingLineChart({ points }) {
  const allVals = points.flatMap((p) => [p.avg_rating_this_year, p.avg_rating_last_year]).filter((v) => v !== null && v !== undefined)
  if (allVals.length === 0) return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No rating data for this range.</div>

  const yMin = Math.max(1, Math.floor((Math.min(...allVals) - 0.15) * 10) / 10)
  const yMax = Math.min(5, Math.ceil((Math.max(...allVals) + 0.15) * 10) / 10)
  const innerW = YOY_LINE_W - YOY_LINE_PAD.left - YOY_LINE_PAD.right
  const innerH = YOY_LINE_H - YOY_LINE_PAD.top - YOY_LINE_PAD.bottom
  const xFor = (i) => YOY_LINE_PAD.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const yFor = (v) => YOY_LINE_PAD.top + innerH - ((v - yMin) / (yMax - yMin)) * innerH

  const segmentsFor = (key) => {
    const segs = []
    let cur = []
    points.forEach((p, i) => {
      const v = p[key]
      if (v !== null && v !== undefined) cur.push([xFor(i), yFor(v)])
      else if (cur.length) { segs.push(cur); cur = [] }
    })
    if (cur.length) segs.push(cur)
    return segs
  }

  const yTicks = []
  for (let v = Math.ceil(yMin * 5) / 5; v <= yMax + 1e-9; v += 0.2) yTicks.push(Math.round(v * 10) / 10)
  const labelEvery = Math.max(1, Math.ceil(points.length / 8))

  return (
    <svg viewBox={`0 0 ${YOY_LINE_W} ${YOY_LINE_H}`} width="100%" style={{ display: 'block' }}>
      {yTicks.map((v) => (
        <g key={v}>
          <line x1={YOY_LINE_PAD.left} x2={YOY_LINE_W - YOY_LINE_PAD.right} y1={yFor(v)} y2={yFor(v)} stroke={SLATE_200} strokeWidth={1} />
          <text x={YOY_LINE_PAD.left - 6} y={yFor(v) + 3} textAnchor="end" fontSize={9} fontFamily={MONO} fill={MUTED}>{v.toFixed(1)}</text>
        </g>
      ))}
      {points.map((p, i) => (
        i % labelEvery === 0 && (
          <text key={p.month} x={xFor(i)} y={YOY_LINE_H - 4} textAnchor="middle" fontSize={9} fontFamily={MONO} fill={MUTED}>{fmtMonth(p.month)}</text>
        )
      ))}
      {segmentsFor('avg_rating_last_year').map((seg, i) => (
        <polyline key={`last-${i}`} fill="none" stroke={SLATE_400} strokeWidth={2} strokeDasharray="4,3" points={seg.map(([x, y]) => `${x},${y}`).join(' ')} />
      ))}
      {segmentsFor('avg_rating_this_year').map((seg, i) => (
        <polyline key={`this-${i}`} fill="none" stroke={DEEP_TEAL} strokeWidth={2} points={seg.map(([x, y]) => `${x},${y}`).join(' ')} />
      ))}
    </svg>
  )
}

function yoySummary(series) {
  const totalThis = series.points.reduce((a, p) => a + p.n_this_year, 0)
  const totalLast = series.points.reduce((a, p) => a + p.n_last_year, 0)
  const pctChange = totalLast ? (totalThis - totalLast) / totalLast : null
  const deltas = series.points.map((p) => p.delta_rating).filter((v) => v !== null && v !== undefined)
  const avgDelta = deltas.length ? deltas.reduce((a, b) => a + b, 0) / deltas.length : null
  return { totalThis, totalLast, pctChange, avgDelta }
}

function YoyLeaderboard({ series, colorByName }) {
  return (
    <div>
      {series.map((s) => {
        const sum = yoySummary(s)
        const positive = sum.pctChange === null ? null : sum.pctChange >= 0
        return (
          <div key={s.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', fontSize: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: colorByName[s.name], display: 'inline-block' }} />
              <span style={{ fontWeight: s.mavis ? 600 : 400 }}>{s.name}</span>
              {s.mavis && <span style={{ color: TEAL_700, fontSize: 9, fontFamily: MONO, fontWeight: 600, paddingLeft: 4 }}>MAVIS</span>}
            </div>
            <div style={{ display: 'flex', gap: 14, fontFamily: MONO, fontSize: 11 }}>
              <span style={{ color: MUTED }}>{fmtNum(sum.totalThis)} vs {fmtNum(sum.totalLast)} reviews</span>
              <span style={{ fontWeight: 600, color: positive === null ? MUTED : positive ? GREEN : ROSE }}>{fmtPct(sum.pctChange)}</span>
              <span style={{ color: MUTED, minWidth: 60, textAlign: 'right' }}>{sum.avgDelta === null ? '' : `${sum.avgDelta >= 0 ? '+' : ''}${sum.avgDelta.toFixed(2)}★`}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ThemeMixChart({ themes, complaintsByTheme, openTheme, onToggle, onSeeReviews }) {
  if (themes === null) return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>Loading…</div>
  if (themes.length === 0) return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No themed reviews in this scope.</div>
  const maxTotal = Math.max(...themes.map((t) => t.total))
  return (
    <div>
      {themes.map((t) => {
        const complaint = complaintsByTheme[t.theme]
        const isOpen = openTheme === t.theme
        return (
          <div key={t.theme} style={{ padding: '6px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 3 }}>
              <span style={{ fontWeight: 600 }}>{THEME_LABELS[t.theme] || t.theme}</span>
              <span style={{ color: MUTED, fontFamily: MONO }}>{t.total} mention{t.total === 1 ? '' : 's'}</span>
            </div>
            <div style={{ display: 'flex', height: 10, borderRadius: 1, overflow: 'hidden', width: `${Math.max(8, (t.total / maxTotal) * 100)}%`, minWidth: 60 }}>
              {t.positive > 0 && <div style={{ width: `${(t.positive / t.total) * 100}%`, background: GREEN }} title={`${t.positive} positive`} />}
              {t.neutral > 0 && <div style={{ width: `${(t.neutral / t.total) * 100}%`, background: SLATE_400 }} title={`${t.neutral} neutral`} />}
              {t.negative > 0 && <div style={{ width: `${(t.negative / t.total) * 100}%`, background: ROSE }} title={`${t.negative} negative`} />}
            </div>
            {t.negative > 0 && (
              <div style={{ marginTop: 5 }}>
                <span onClick={() => onToggle(t.theme)} style={{ fontSize: 10, color: ROSE, cursor: 'pointer', fontWeight: 600 }}>
                  {isOpen ? 'Hide complaint summary ▲' : `What's the complaint? (${t.negative} negative) →`}
                </span>
                {isOpen && (
                  <div style={{ marginTop: 6, background: '#FDF2F4', borderLeft: `3px solid ${ROSE}`, borderRadius: 4, padding: '9px 11px', fontSize: 11.5, lineHeight: 1.55, color: INK_TEXT, maxWidth: '70ch' }}>
                    {!complaint || complaint.loading ? 'Summarizing…' : complaint.summary || 'Not enough negative reviews in this scope to summarize.'}
                    {complaint && !complaint.loading && (
                      <div style={{ marginTop: 8 }}>
                        <span onClick={() => onSeeReviews(t.theme)} style={{ fontSize: 10.5, color: DEEP_TEAL, cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}>
                          See all these reviews ↓
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function ReviewCard({ r }) {
  const sentColor = r.sentiment === 'positive' ? GREEN : r.sentiment === 'negative' ? ROSE : SLATE_400
  return (
    <div style={{ padding: '10px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 4 }}>
        <div style={{ fontSize: 12 }}>
          <span style={{ fontWeight: 600 }}>{r.brand}</span>
          {r.mavis && <span style={{ color: TEAL_700, fontSize: 9.5, fontFamily: MONO, fontWeight: 600, paddingLeft: 6 }}>MAVIS</span>}
          <span style={{ color: MUTED }}> · {r.city} · {r.date}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 'none' }}>
          <span style={{ fontFamily: MONO, fontWeight: 600, fontSize: 12 }}>{r.rating}★</span>
          <span style={{ fontSize: 9.5, fontWeight: 600, color: '#FFFFFF', background: sentColor, borderRadius: 4, padding: '2px 6px', textTransform: 'uppercase', letterSpacing: '.04em' }}>
            {r.sentiment || 'pending'}
          </span>
        </div>
      </div>
      <div style={{ fontSize: 12, color: INK_TEXT, lineHeight: 1.45, marginBottom: 3 }}>{r.text}</div>
      <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>{r.reason}</div>
    </div>
  )
}

export default function VoiceReviewTrend() {
  const [reviewStates, setReviewStates] = useState([])
  const [stateFilter, setStateFilter] = useState('TX')
  const [towns, setTowns] = useState([])
  const [cityFilter, setCityFilter] = useState('')
  const [splitCompetitors, setSplitCompetitors] = useState(false)
  const [visibleCompetitors, setVisibleCompetitors] = useState(null) // null = show all

  const [trend, setTrend] = useState(null)
  const [yoy, setYoy] = useState(null)
  const [error, setError] = useState(null)

  const [detailSeries, setDetailSeries] = useState(null)
  const [snapshotMonth, setSnapshotMonth] = useState(null)
  const [snapshotView, setSnapshotView] = useState('trend12') // 'month' (bar) | 'trend12' (line, trailing 12mo)
  const [themeMix, setThemeMix] = useState(null)
  const [complaintsByTheme, setComplaintsByTheme] = useState({})
  const [openComplaintTheme, setOpenComplaintTheme] = useState(null)

  const [sampleBrand, setSampleBrand] = useState('')
  const [sampleSentiment, setSampleSentiment] = useState('')
  const [sampleTheme, setSampleTheme] = useState('')
  const [sampleRating, setSampleRating] = useState('')
  const [samples, setSamples] = useState(null)

  useEffect(() => {
    api.voiceReviewStates().then((rs) => {
      setReviewStates(rs)
      if (rs.length && !rs.some((s) => s.state === 'TX')) setStateFilter(rs[0].state)
    }).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    let cancelled = false
    setCityFilter('')
    api.voiceReviewTowns(stateFilter).then((t) => { if (!cancelled) setTowns(t) }).catch(() => { if (!cancelled) setTowns([]) })
    return () => { cancelled = true }
  }, [stateFilter])

  useEffect(() => {
    let cancelled = false
    setTrend(null)
    api.voiceReviewTrend(stateFilter, cityFilter || undefined, splitCompetitors).then((d) => {
      if (cancelled) return
      setTrend(d)
      setVisibleCompetitors(null)
      const firstMavis = d.series.find((s) => s.mavis)
      setDetailSeries((prev) => (d.series.some((s) => s.name === prev) ? prev : (firstMavis ? firstMavis.name : d.series[0]?.name || null)))
    }).catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [stateFilter, cityFilter, splitCompetitors])

  useEffect(() => {
    let cancelled = false
    setYoy(null)
    api.voiceReviewYoy(stateFilter, cityFilter || undefined, splitCompetitors).then((d) => { if (!cancelled) setYoy(d) }).catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [stateFilter, cityFilter, splitCompetitors])

  useEffect(() => {
    let cancelled = false
    setThemeMix(null)
    // A prior scope's complaint summaries don't apply once state/city/brand
    // changes what "negative reviews for this theme" even means.
    setComplaintsByTheme({})
    setOpenComplaintTheme(null)
    const brand = detailSeries && detailSeries !== 'Competitors' ? detailSeries : undefined
    api.voiceReviewThemeMix(stateFilter, { city: cityFilter || undefined, brand }).then((d) => { if (!cancelled) setThemeMix(d) }).catch(() => { if (!cancelled) setThemeMix([]) })
    return () => { cancelled = true }
  }, [stateFilter, cityFilter, detailSeries])

  // Live, on-demand only (not fetched for every theme up front) - a real
  // Haiku call per theme, so it only runs for themes the user actually
  // opens.
  const toggleComplaint = (theme) => {
    if (openComplaintTheme === theme) { setOpenComplaintTheme(null); return }
    setOpenComplaintTheme(theme)
    if (complaintsByTheme[theme]) return
    setComplaintsByTheme((prev) => ({ ...prev, [theme]: { loading: true } }))
    const brand = detailSeries && detailSeries !== 'Competitors' ? detailSeries : undefined
    api.voiceReviewThemeComplaints(theme, stateFilter, { city: cityFilter || undefined, brand })
      .then((d) => setComplaintsByTheme((prev) => ({ ...prev, [theme]: { loading: false, summary: d.summary } })))
      .catch(() => setComplaintsByTheme((prev) => ({ ...prev, [theme]: { loading: false, summary: null } })))
  }

  useEffect(() => {
    let cancelled = false
    setSamples(null)
    api.voiceReviewSample(stateFilter, {
      city: cityFilter || undefined, brand: sampleBrand || undefined,
      sentiment: sampleSentiment || undefined, theme: sampleTheme || undefined,
      rating: sampleRating || undefined, limit: 25,
    })
      .then((d) => { if (!cancelled) setSamples(d) })
      .catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [stateFilter, cityFilter, sampleBrand, sampleSentiment, sampleTheme, sampleRating])

  // "See all reviews" from a theme's complaint summary - jump to the
  // browsable list below, pre-filtered to exactly the reviews that
  // summary was built from (same brand/state/city, that theme, negative).
  const reviewsSectionRef = useRef(null)
  const jumpToReviewsForTheme = (theme) => {
    setSampleBrand(detailSeries && detailSeries !== 'Competitors' ? detailSeries : '')
    setSampleSentiment('negative')
    setSampleTheme(theme)
    reviewsSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const brandOptions = trend?.series.map((s) => s.name) || []
  const competitorNames = useMemo(() => (trend?.series || []).filter((s) => !s.mavis).map((s) => s.name), [trend])
  const visibleSet = visibleCompetitors === null ? new Set(competitorNames) : visibleCompetitors
  const displayedTrendSeries = useMemo(
    () => (trend?.series || []).filter((s) => s.mavis || visibleSet.has(s.name)),
    [trend, visibleSet]
  )
  const displayedYoySeries = useMemo(
    () => (yoy?.series || []).filter((s) => s.mavis || visibleSet.has(s.name)),
    [yoy, visibleSet]
  )
  const trendColors = useSeriesColors(trend?.series || [])
  const totalReviews = trend?.series.reduce((sum, s) => sum + s.points.reduce((a, p) => a + p.n_reviews, 0), 0) || 0

  const snapshotMonths = useMemo(() => {
    const set = new Set()
    displayedTrendSeries.forEach((s) => s.points.forEach((p) => { if (p.n_reviews > 0) set.add(p.month) }))
    return [...set].sort()
  }, [displayedTrendSeries])

  useEffect(() => {
    if (!snapshotMonths.length) return
    setSnapshotMonth((prev) => (prev && snapshotMonths.includes(prev) ? prev : snapshotMonths[snapshotMonths.length - 1]))
  }, [snapshotMonths])

  // A tighter window than "Average rating over time" below (which shows the
  // whole scrape history, 2+ years) - just the trailing 12 calendar months,
  // per the user's own framing of this as a separate, shorter-range view.
  const last12Series = useMemo(() => {
    const last12 = snapshotMonths.slice(-12)
    const cutoff = new Set(last12)
    return displayedTrendSeries.map((s) => ({ ...s, points: s.points.filter((p) => cutoff.has(p.month)) }))
  }, [displayedTrendSeries, snapshotMonths])

  const toggleCompetitor = (name) => {
    setVisibleCompetitors((prev) => {
      const base = prev === null ? new Set(competitorNames) : new Set(prev)
      if (base.has(name)) base.delete(name)
      else base.add(name)
      return base
    })
  }

  const detailTrendSeries = trend?.series.find((s) => s.name === detailSeries)
  const detailYoySeries = yoy?.series.find((s) => s.name === detailSeries)

  // Spelled out per-section below, since which of the filters up top
  // actually apply to a given chart isn't otherwise obvious (the
  // competitor-view toggle only affects charts with a Mavis-vs-competitor
  // line/bar shape, not the per-brand theme/sentiment views).
  const stateLabel = reviewStates.find((s) => s.state === stateFilter)?.state_name || stateFilter
  const cityLabel = cityFilter || 'all towns'
  const competitorLabel = splitCompetitors ? 'by competitor' : 'blended competitors'

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
        <div style={{ fontSize: 11, color: MUTED, maxWidth: '55ch' }}>
          Individual Google reviews, sentiment-classified from the review text. {fmtNum(totalReviews)} reviews in this scope.
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} style={selectStyle()}>
            {reviewStates.map((s) => <option key={s.state} value={s.state}>{s.state_name}</option>)}
          </select>
          <select value={cityFilter} onChange={(e) => setCityFilter(e.target.value)} style={selectStyle()}>
            <option value="">All towns</option>
            {towns.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button onClick={() => setSplitCompetitors(false)} style={pillStyle(!splitCompetitors)}>Blended competitors</button>
          <button onClick={() => setSplitCompetitors(true)} style={pillStyle(splitCompetitors)}>By competitor</button>
        </div>
      </div>

      {error ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>
      ) : trend === null ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : trend.series.length === 0 ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>No reviews scraped yet for this scope.</div>
      ) : (
        <>
          <Section title="Average rating" scope={`Filtered by ${stateLabel} · ${cityLabel} · ${competitorLabel} (filters above)`}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, flexWrap: 'wrap', gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{snapshotView === 'month' ? 'Average rating that month' : 'Average rating - last 12 months'}</div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <button onClick={() => setSnapshotView('month')} style={pillStyle(snapshotView === 'month')}>Snapshot</button>
                <button onClick={() => setSnapshotView('trend12')} style={pillStyle(snapshotView === 'trend12')}>Line (12mo)</button>
                {snapshotView === 'month' && (
                  <select value={snapshotMonth || ''} onChange={(e) => setSnapshotMonth(e.target.value)} style={selectStyle()}>
                    {snapshotMonths.map((m) => <option key={m} value={m}>{fmtMonth(m)}</option>)}
                  </select>
                )}
              </div>
            </div>
            {snapshotView === 'month' ? (
              <>
                <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 8 }}>Every brand's own average for this one month - a snapshot, not a trend.</div>
                <MonthlySnapshotChart series={displayedTrendSeries} month={snapshotMonth} colorByName={trendColors} />
              </>
            ) : (
              <>
                <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 8 }}>Just the trailing 12 months - a tighter window than the full history below.</div>
                <RatingTrendChart series={last12Series} colorByName={trendColors} />
                <Legend series={last12Series} colorByName={trendColors} />
              </>
            )}

            <RowDivider />

            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Average rating over time</div>
            <RatingTrendChart series={displayedTrendSeries} colorByName={trendColors} />
            <Legend series={displayedTrendSeries} colorByName={trendColors} />
            {splitCompetitors && (
              <CompetitorChecklist
                names={competitorNames} visible={visibleSet} onToggle={toggleCompetitor}
                onAll={() => setVisibleCompetitors(new Set(competitorNames))} onNone={() => setVisibleCompetitors(new Set())}
              />
            )}
          </Section>

          <Section title="Year-over-year" scope={`Filtered by ${stateLabel} · ${cityLabel} · ${competitorLabel} (filters above) · one brand at a time below`}>
            <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 8 }}>How each brand's trailing 12 months compares to the same 12 months a year earlier.</div>
            {yoy === null ? (
              <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>Loading…</div>
            ) : (
              <>
                <YoyLeaderboard series={displayedYoySeries} colorByName={trendColors} />
                {detailYoySeries && (
                  <div style={{ marginTop: 14 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4, flexWrap: 'wrap', gap: 8 }}>
                      <div style={{ fontSize: 11.5, fontWeight: 600, color: SLATE_600 }}>Avg rating - <strong style={{ color: INK_TEXT }}>{detailSeries}</strong></div>
                      <select value={detailSeries || ''} onChange={(e) => setDetailSeries(e.target.value)} style={selectStyle()}>
                        {brandOptions.map((b) => <option key={b} value={b}>{b}</option>)}
                      </select>
                    </div>
                    <YoyRatingLineChart points={detailYoySeries.points} />
                    <div style={{ display: 'flex', gap: 14, fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 4, marginBottom: 16 }}>
                      <span style={{ color: DEEP_TEAL }}>— this year</span>
                      <span style={{ color: SLATE_400 }}>┄┄ last year</span>
                    </div>

                    <div style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 6, color: SLATE_600 }}>Review volume - <strong style={{ color: INK_TEXT }}>{detailSeries}</strong></div>
                    <YoyBarChart points={detailYoySeries.points} />
                    <div style={{ display: 'flex', gap: 14, fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 4 }}>
                      <span style={{ color: DEEP_TEAL }}>■ this year</span>
                      <span style={{ color: SLATE_400 }}>■ last year</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </Section>

          <Section title="Sentiment & themes" scope={`Filtered by ${stateLabel} · ${cityLabel} (filters above) · one brand at a time below — the competitor-view toggle above doesn't apply here`}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
              <div style={{ fontSize: 11.5, color: MUTED }}>Showing <strong style={{ color: INK_TEXT }}>{detailSeries}</strong></div>
              <select value={detailSeries || ''} onChange={(e) => setDetailSeries(e.target.value)} style={selectStyle()}>
                {brandOptions.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </div>

            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Sentiment mix over time</div>
            {detailTrendSeries && <SentimentMixChart points={detailTrendSeries.points} />}
            <div style={{ display: 'flex', gap: 14, fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 8, marginBottom: 20 }}>
              <span style={{ color: GREEN }}>■ positive</span>
              <span style={{ color: SLATE_400 }}>■ neutral</span>
              <span style={{ color: ROSE }}>■ negative</span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2, flexWrap: 'wrap', gap: 8 }}>
              <div style={{ fontSize: 13, fontWeight: 600 }}>What people are talking about</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} style={selectStyle()}>
                  {reviewStates.map((s) => <option key={s.state} value={s.state}>{s.state_name}</option>)}
                </select>
                <select value={cityFilter} onChange={(e) => setCityFilter(e.target.value)} style={selectStyle()}>
                  <option value="">All towns</option>
                  {towns.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <select value={detailSeries || ''} onChange={(e) => setDetailSeries(e.target.value)} style={selectStyle()}>
                  {brandOptions.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </div>
            </div>
            <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 8 }}>
              Sentiment mix broken down by theme (price, speed, friendliness, etc.) - extracted from review text, not just star count.
              Themes with negative mentions can be expanded into a summary of the specific complaints.
            </div>
            <ThemeMixChart
              themes={themeMix} complaintsByTheme={complaintsByTheme} openTheme={openComplaintTheme}
              onToggle={toggleComplaint} onSeeReviews={jumpToReviewsForTheme}
            />
          </Section>

          <Section
            title="What people are saying" sectionRef={reviewsSectionRef}
            scope={`Filtered by ${stateLabel} · ${cityLabel} (filters above) · brand, star rating, sentiment, and issue filters below are local to this list`}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <select
                  value={sampleBrand} onChange={(e) => setSampleBrand(e.target.value)}
                  style={selectStyle()}
                >
                  <option value="">All brands</option>
                  {brandOptions.filter((b) => b !== 'Competitors').map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
                <select value={sampleRating} onChange={(e) => setSampleRating(e.target.value)} style={selectStyle()}>
                  <option value="">All ratings</option>
                  {[5, 4, 3, 2, 1].map((n) => <option key={n} value={n}>{n}★</option>)}
                </select>
                <select value={sampleTheme} onChange={(e) => setSampleTheme(e.target.value)} style={selectStyle()}>
                  <option value="">All issues</option>
                  {Object.entries(THEME_LABELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                </select>
                {['', 'positive', 'neutral', 'negative'].map((s) => (
                  <button key={s || 'all'} onClick={() => setSampleSentiment(s)} style={pillStyle(sampleSentiment === s)}>
                    {s || 'All sentiment'}
                  </button>
                ))}
              </div>
            </div>
            <div style={{ background: TEAL_WASH, borderRadius: 8, padding: '4px 14px', maxHeight: 480, overflowY: 'auto' }}>
              {samples === null ? (
                <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>Loading…</div>
              ) : samples.length === 0 ? (
                <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No reviews match this filter.</div>
              ) : (
                samples.map((r, i) => (
                  <div key={i}>
                    <ReviewCard r={r} />
                    {i < samples.length - 1 && <div style={{ height: 1, background: '#D8E6E7' }} />}
                  </div>
                ))
              )}
            </div>
          </Section>
        </>
      )}
    </div>
  )
}
