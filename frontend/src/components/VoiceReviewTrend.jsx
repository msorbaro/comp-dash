import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { RowDivider } from './Widgets'
import {
  MUTED, INK_TEXT, SLATE_600, SLATE_200, SLATE_400, DEEP_TEAL, TEAL_700, TEAL_WASH,
  MONO, GREEN, ROSE, ATTRIBUTE_COLORS, fmtNum,
} from '../styles'

// Fixed hue order, reusing the app's own established categorical palette
// (already validated for this design system) rather than inventing a new
// one for a single chart - the catch-all gray in that palette is reserved
// here for the "Competitors" aggregate line below.
const MAVIS_LINE_COLORS = Object.values(ATTRIBUTE_COLORS).slice(0, -1)
const COMPETITOR_COLOR = SLATE_600

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

function fmtMonth(iso) {
  const [y, m] = iso.split('-')
  return new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })
}

function fmtRating(v) {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

const CHART_W = 900
const CHART_H = 260
const PAD = { top: 14, right: 16, bottom: 28, left: 34 }

function RatingTrendChart({ series }) {
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

  const allRatings = series.flatMap((s) => s.points.map((p) => p.avg_rating).filter((v) => v !== null))
  const yMin = Math.max(1, Math.floor((Math.min(...allRatings) - 0.15) * 10) / 10)
  const yMax = Math.min(5, Math.ceil((Math.max(...allRatings) + 0.15) * 10) / 10)

  const innerW = CHART_W - PAD.left - PAD.right
  const innerH = CHART_H - PAD.top - PAD.bottom
  const xFor = (i) => PAD.left + (months.length === 1 ? innerW / 2 : (i / (months.length - 1)) * innerW)
  const yFor = (v) => PAD.top + innerH - ((v - yMin) / (yMax - yMin)) * innerH

  const yTicks = []
  for (let v = Math.ceil(yMin * 5) / 5; v <= yMax + 1e-9; v += 0.2) yTicks.push(Math.round(v * 10) / 10)

  // Show at most ~8 month labels on the x-axis so they never collide.
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
          const color = s.mavis ? MAVIS_LINE_COLORS[si % MAVIS_LINE_COLORS.length] : COMPETITOR_COLOR
          const pts = months
            .map((m, i) => {
              const p = pointByMonth[si][m]
              return p && p.avg_rating !== null ? [xFor(i), yFor(p.avg_rating)] : null
            })
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
          borderRadius: 8, padding: '8px 10px', fontSize: 11, boxShadow: '0 2px 8px rgba(15,20,24,.08)', minWidth: 160,
        }}>
          <div style={{ fontWeight: 600, marginBottom: 5 }}>{fmtMonth(hoverMonth)}</div>
          {series.map((s, si) => {
            const p = pointByMonth[si][hoverMonth]
            const color = s.mavis ? MAVIS_LINE_COLORS[si % MAVIS_LINE_COLORS.length] : COMPETITOR_COLOR
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

function Legend({ series }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginTop: 10 }}>
      {series.map((s, i) => {
        const color = s.mavis ? MAVIS_LINE_COLORS[i % MAVIS_LINE_COLORS.length] : COMPETITOR_COLOR
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

export default function VoiceReviewTrend({ states }) {
  const [trend, setTrend] = useState(null)
  const [error, setError] = useState(null)
  const [sentimentBrand, setSentimentBrand] = useState(null)
  const [sampleBrand, setSampleBrand] = useState('')
  const [sampleSentiment, setSampleSentiment] = useState('')
  const [samples, setSamples] = useState(null)

  const stateName = useMemo(
    () => Object.fromEntries((states || []).map((s) => [s.state, s.state_name])),
    [states]
  )

  useEffect(() => {
    api.voiceReviewTrend('TX').then((d) => {
      setTrend(d)
      const firstMavis = d.series.find((s) => s.mavis)
      setSentimentBrand(firstMavis ? firstMavis.name : d.series[0]?.name || null)
    }).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    let cancelled = false
    setSamples(null)
    api.voiceReviewSample('TX', { brand: sampleBrand || undefined, sentiment: sampleSentiment || undefined, limit: 25 })
      .then((d) => { if (!cancelled) setSamples(d) })
      .catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [sampleBrand, sampleSentiment])

  const brandOptions = trend?.series.map((s) => s.name) || []
  const sentimentSeries = trend?.series.find((s) => s.name === sentimentBrand)
  const totalReviews = trend?.series.reduce((sum, s) => sum + s.points.reduce((a, p) => a + p.n_reviews, 0), 0) || 0

  return (
    <div>
      <div style={{ fontSize: 11, color: MUTED, marginBottom: 14, maxWidth: '70ch' }}>
        Individual Google reviews (last 2 years, Texas), sentiment-classified from the review text. {fmtNum(totalReviews)} reviews so far — this scrape runs in batches and fills in over time.
      </div>

      {error ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>
      ) : trend === null ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : trend.series.length === 0 ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>No reviews scraped yet for {stateName.TX || 'Texas'}.</div>
      ) : (
        <>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Average rating over time</div>
          <RatingTrendChart series={trend.series} />
          <Legend series={trend.series} />

          <RowDivider />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Sentiment mix over time</div>
            <select
              value={sentimentBrand || ''}
              onChange={(e) => setSentimentBrand(e.target.value)}
              style={{ fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }}
            >
              {brandOptions.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          {sentimentSeries && <SentimentMixChart points={sentimentSeries.points} />}
          <div style={{ display: 'flex', gap: 14, fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 8 }}>
            <span style={{ color: GREEN }}>■ positive</span>
            <span style={{ color: SLATE_400 }}>■ neutral</span>
            <span style={{ color: ROSE }}>■ negative</span>
          </div>

          <RowDivider />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>What people are saying</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <select
                value={sampleBrand} onChange={(e) => setSampleBrand(e.target.value)}
                style={{ fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }}
              >
                <option value="">All brands</option>
                {brandOptions.filter((b) => b !== 'Competitors').map((b) => <option key={b} value={b}>{b}</option>)}
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
        </>
      )}
    </div>
  )
}
