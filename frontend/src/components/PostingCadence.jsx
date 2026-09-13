import { useEffect, useState } from 'react'
import { api } from '../api'
import { fmtNum, STAGES, ATTRIBUTE_COLORS, ATTRIBUTE_ORDER, CHANNEL_ORDER, CHANNEL_COLORS, CHANNEL_NAME, MUTED, INK_TEXT, SLATE_600, SLATE_200, DEEP_TEAL, TRACK } from '../styles'

const BAR_HEIGHT = 170
const DAY_OPTIONS = [30, 90, 180]
const MODES = [
  { key: 'stage', label: 'By stage' },
  { key: 'attribute', label: 'By attribute' },
  { key: 'channel', label: 'By channel' },
]

function orderFor(mode) {
  if (mode === 'stage') return STAGES.map((s) => s.name)
  if (mode === 'channel') return CHANNEL_ORDER
  return ATTRIBUTE_ORDER
}
function colorFor(mode, key) {
  if (mode === 'stage') return STAGES.find((s) => s.name === key)?.color
  if (mode === 'channel') return CHANNEL_COLORS[key]
  return ATTRIBUTE_COLORS[key]
}
function labelFor(mode, key) {
  return mode === 'channel' ? CHANNEL_NAME[key] : key
}
function byKey(mode, r) {
  if (mode === 'stage') return r.by_stage
  if (mode === 'channel') return r.by_channel
  return r.by_attribute
}

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
        background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
        border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
      }}
    >
      {children}
    </button>
  )
}

// One bar per company, stacked and colored by stage, real classified message
// attribute, or channel - "count" stacks to each company's actual volume (so
// cadence differences are visible in bar height); "pct" stacks every bar to
// a shared 100% (so composition is comparable regardless of how often a
// company posts at all). Full page width, one row - bars get their own
// natural width instead of being squeezed into a half-width column, which is
// what caused the previous side-by-side layout to run off screen for
// categories with more companies.
function VolumeByCompanyChart({ rows, mode, view }) {
  const order = orderFor(mode)
  const maxTotal = Math.max(...rows.map((r) => r.total), 1)
  const presentKeys = order.filter((k) => rows.some((r) => (byKey(mode, r)[k] || 0) > 0))

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 14, fontSize: 10, color: MUTED }}>
        {presentKeys.map((k) => (
          <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: colorFor(mode, k), display: 'inline-block', flex: 'none' }} />
            {labelFor(mode, k)}
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap' }}>
        {rows.map((r) => {
          const keyed = byKey(mode, r)
          const classifiedTotal = order.reduce((s, k) => s + (keyed[k] || 0), 0)
          const segments = order.map((k) => ({ key: k, count: keyed[k] || 0 })).filter((s) => s.count > 0)
          return (
            <div key={r.company} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 78, flex: 'none' }}>
              <div style={{ display: 'flex', flexDirection: 'column-reverse', width: 38, height: BAR_HEIGHT, borderRadius: 4, overflow: 'hidden', background: TRACK }}>
                {segments.map((s) => {
                  const heightPx = view === 'pct'
                    ? (classifiedTotal ? (s.count / classifiedTotal) * BAR_HEIGHT : 0)
                    : (maxTotal ? (s.count / maxTotal) * BAR_HEIGHT : 0)
                  const pct = classifiedTotal ? Math.round((s.count / classifiedTotal) * 100) : 0
                  return (
                    <div
                      key={s.key}
                      title={`${r.company} — ${labelFor(mode, s.key)}: ${s.count} (${pct}% of classified output)`}
                      style={{ height: `${heightPx}px`, background: colorFor(mode, s.key), borderTop: '2px solid #FFFFFF' }}
                    />
                  )
                })}
              </div>
              <div style={{ fontSize: 9.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace', marginTop: 6 }}>{fmtNum(r.total)}</div>
              <div style={{ fontSize: 9.5, color: INK_TEXT, textAlign: 'center', marginTop: 3, lineHeight: 1.25, overflowWrap: 'break-word' }}>{r.company}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function GroupPanel({ title, rows, mode, view }) {
  if (!rows?.length) return <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>No data for this group yet.</div>
  return (
    <div>
      <div style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 10 }}>{title}</div>
      <VolumeByCompanyChart rows={rows} mode={mode} view={view} />
    </div>
  )
}

const selectStyle = {
  fontSize: 11, fontWeight: 600, padding: '5px 10px', borderRadius: 7, border: `1px solid ${SLATE_200}`,
  color: DEEP_TEAL, background: '#FFFFFF', fontFamily: 'Poppins, sans-serif', cursor: 'pointer',
}

// A small caption above each pill row so it's clear which buttons act as
// one group (which one is "on") vs. just a loose row of unrelated buttons.
const groupLabelStyle = { fontSize: 9, letterSpacing: '.1em', color: MUTED, fontWeight: 600, marginBottom: 6 }

// Self-contained: fetches its own two datasets - Our Brands (fixed) and a
// selectable comparison category (default: Automotive Full Service, the
// closest direct-competitor set) - and owns the toggle state, so
// Landscape.jsx just drops this section in.
export default function PostingCadence({ categories }) {
  const [days, setDays] = useState(90)
  const [mode, setMode] = useState('attribute')
  const [view, setView] = useState('count')
  const [compareCategory, setCompareCategory] = useState('Automotive Full Service')
  const [ours, setOurs] = useState(null)
  const [compared, setCompared] = useState(null)
  const [error, setError] = useState(null)

  const compareOptions = categories.filter((c) => c !== 'Our Brands')
  const effectiveCompareCategory = compareOptions.includes(compareCategory) ? compareCategory : (compareOptions[0] || '')

  const load = () => {
    setError(null)
    Promise.all([
      api.landscapeVolume('Our Brands', days),
      effectiveCompareCategory ? api.landscapeVolume(effectiveCompareCategory, days) : Promise.resolve(null),
    ]).then(([a, b]) => { setOurs(a); setCompared(b) }).catch((e) => setError(e.message))
  }
  useEffect(load, [days, effectiveCompareCategory])

  return (
    <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 4 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Posting cadence by company</div>
          <div style={{ fontSize: 11, color: MUTED, maxWidth: 560 }}>
            How often each company posts, and what that output is made of - the Mavis family against any category you pick.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          <div>
            <div style={groupLabelStyle}>TIME WINDOW</div>
            <div style={{ display: 'flex', gap: 5 }}>
              {DAY_OPTIONS.map((d) => (
                <Pill key={d} active={days === d} onClick={() => setDays(d)}>{d}d</Pill>
              ))}
            </div>
          </div>
          <div>
            <div style={groupLabelStyle}>BREAK DOWN BY</div>
            <div style={{ display: 'flex', gap: 5 }}>
              {MODES.map((m) => (
                <Pill key={m.key} active={mode === m.key} onClick={() => setMode(m.key)}>{m.label}</Pill>
              ))}
            </div>
          </div>
          <div>
            <div style={groupLabelStyle}>SHOW AS</div>
            <div style={{ display: 'flex', gap: 5 }}>
              <Pill active={view === 'count'} onClick={() => setView('count')}>Volume</Pill>
              <Pill active={view === 'pct'} onClick={() => setView('pct')}>Mix %</Pill>
            </div>
          </div>
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
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24, marginTop: 18 }}>
          <GroupPanel title="Mavis family of brands" rows={ours.rows} mode={mode} view={view} />
          <div style={{ height: 1, background: SLATE_200 }} />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
              <span style={{ fontSize: 11.5, fontWeight: 600 }}>Compare against</span>
              <select value={effectiveCompareCategory} onChange={(e) => setCompareCategory(e.target.value)} style={selectStyle}>
                {compareOptions.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <VolumeByCompanyChart rows={compared.rows} mode={mode} view={view} />
          </div>
        </div>
      )}
    </div>
  )
}
