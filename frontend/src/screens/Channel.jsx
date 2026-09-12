import { useEffect, useState } from 'react'
import { api } from '../api'
import { SectionNumber, StageBar, MixCaption, ReadLine, CreativeCard, InfoLabel } from '../components/Widgets'
import {
  paidChipStyle, fmtNum, dominantIdx, dominantWord, engagementUnitLabel,
  STAGES, MUTED, INK_TEXT, SLATE_600, SLATE_200, TEAL_700, TRACK, DEEP_TEAL,
} from '../styles'

// This page's copy literally says "every piece of creative we captured", and
// a stage/type filter must be able to find any item that contributed to its
// own percentage - so fetch everything (a channel tops out around 40 items
// in practice), not a capped preview like the Brand-page section grids use.
const CREATIVE_FETCH_N = 500

export default function Channel({ brand, category, channelId, onBack, initialTypeFilter = null }) {
  const [data, setData] = useState(null)
  const [stageFilter, setStageFilter] = useState(null)
  const [typeFilter, setTypeFilter] = useState(initialTypeFilter)

  useEffect(() => {
    setData(null)
    setStageFilter(null)
    setTypeFilter(initialTypeFilter)
    api.channel(brand, channelId, CREATIVE_FETCH_N).then(setData)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brand, channelId])

  if (!data) return <div style={{ padding: 40, color: MUTED }}>Loading…</div>
  const r = data.channel_data
  const ch = r.channel
  const topCt = r.content_types.length ? [...r.content_types].sort((a, b) => b.pct - a.pct)[0].name.toLowerCase() : 'unclassified content'
  const idx = dominantIdx(r.split)
  const takeaway = r.read_line || (`${r.split[idx]}% ${dominantWord(r.split).replace('-led', '')}. Led by ${topCt} ` +
    `(${r.total_all_time} tracked, ~${r.monthly_avg_all_time}/mo).`)

  const filtered = data.creatives.filter(
    (cr) => (!stageFilter || cr.stage === stageFilter) && (!typeFilter || cr.type === typeFilter)
  )

  return (
    <div>
      <SectionNumber num="03" title="Channel Detail" />
      <div style={{ fontSize: 11, color: MUTED, marginBottom: 10 }}>
        / {brand} / <b style={{ color: INK_TEXT }}>{ch.name}</b>
      </div>
      <button onClick={onBack} style={{ background: 'none', border: 'none', color: TEAL_700, cursor: 'pointer', fontSize: 12, padding: 0, marginBottom: 16, fontFamily: 'Poppins, sans-serif' }}>
        ← back to all channels
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1fr', gap: 14, marginBottom: 14 }}>
        <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '22px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ margin: 0, fontSize: 26, fontWeight: 600 }}>{ch.name}</h1>
            <div style={paidChipStyle(ch.paid)}>{ch.paid ? 'PAID' : 'OWNED / ORGANIC'}</div>
          </div>
          <div style={{ fontSize: 12, color: SLATE_600, marginTop: 6 }}>{brand} · {category}</div>
          <div style={{ marginTop: 14 }}><ReadLine text={takeaway} /></div>
          <div style={{ fontSize: 10.5, color: MUTED, marginTop: 8 }}>
            Click a stage below to filter the creative evidence to just that stage.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginTop: 10 }}>
            {STAGES.map((s, i) => {
              const active = stageFilter === s.name
              return (
                <button
                  key={s.id}
                  onClick={() => setStageFilter(active ? null : s.name)}
                  style={{
                    textAlign: 'left', cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
                    background: active ? '#FAFBFC' : '#FFFFFF', border: `1px solid ${active ? s.color : SLATE_200}`,
                    borderTop: `3px solid ${s.color}`, borderRadius: 10, padding: '14px 15px',
                    boxShadow: active ? `0 0 0 1px ${s.color}` : 'none',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '.1em', color: SLATE_600 }}>{s.name.toUpperCase()}</div>
                    <div style={{ fontSize: 22, fontWeight: 600, color: s.color }}>{r.split[i]}%</div>
                  </div>
                  <div style={{ marginTop: 11 }}>
                    {r.stage_summaries?.[s.name] ? (
                      <div style={{ fontSize: 11, color: INK_TEXT, lineHeight: 1.45, padding: '7px 9px', background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 7 }}>
                        {r.stage_summaries[s.name]}
                      </div>
                    ) : <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>
                      {r.total_all_time > 0 ? 'summarizing…' : 'no examples yet'}
                    </div>}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '18px 19px' }}>
            <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>
              <InfoLabel text="TOTAL POSTED" tooltip="All-time total tracked for this channel, plus the long-run monthly average (total ÷ months tracked)." />
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 6 }}>
              <div style={{ fontSize: 30, fontWeight: 600 }}>{r.total_all_time}</div><div style={{ fontSize: 11, color: MUTED }}>{ch.unit}</div>
            </div>
            <div style={{ fontSize: 11, marginTop: 4, color: MUTED }}>
              ~{r.monthly_avg_all_time}/mo avg{r.last_posted ? ` · last posted ${r.last_posted}` : ''}
            </div>
            <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, margin: '18px 0 2px' }}>CADENCE · 12 WEEKS</div>
            <div style={{ fontSize: 9, color: MUTED, marginBottom: 6 }}>Y: {ch.unit} per week · X: week-starting date</div>
            <Sparkline weeks={r.weeks} labels={r.week_labels} height={56} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 18 }}>
              <div>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>AVG. ENGAGEMENT</div>
                <div style={{ fontSize: 19, fontWeight: 600, marginTop: 4 }}>{r.engagement != null ? fmtNum(r.engagement) : '—'}</div>
                <div style={{ fontSize: 9.5, color: MUTED, marginTop: 1 }}>{engagementUnitLabel(ch.id)}</div>
              </div>
              <div title="Share of this brand's total 90-day output across all channels that this one channel accounts for.">
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>SHARE OF OUTPUT (90D)</div>
                <div style={{ fontSize: 19, fontWeight: 600, marginTop: 4 }}>{r.share != null ? `${r.share}%` : '—'}</div>
              </div>
            </div>
          </div>
          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '18px 19px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 11 }}>
              <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>CONTENT TYPES</div>
              {typeFilter && (
                <button onClick={() => setTypeFilter(null)} style={{ background: 'none', border: 'none', color: TEAL_700, fontSize: 10, cursor: 'pointer', fontFamily: 'Poppins, sans-serif' }}>
                  clear filter
                </button>
              )}
            </div>
            <div style={{ fontSize: 10, color: MUTED, marginBottom: 9, marginTop: -6 }}>Click a type to filter the creative evidence.</div>
            {r.content_types.slice(0, 5).map((ct) => {
              const active = typeFilter === ct.name
              return (
                <button
                  key={ct.name}
                  onClick={() => setTypeFilter(active ? null : ct.name)}
                  style={{ display: 'block', width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: 0, marginBottom: 9, cursor: 'pointer', fontFamily: 'Poppins, sans-serif' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4, color: active ? DEEP_TEAL : INK_TEXT, fontWeight: active ? 600 : 400 }}>
                    <span>{ct.name}</span><span style={{ color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{ct.pct}%</span>
                  </div>
                  <div style={{ height: 6, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${ct.pct}%`, background: active ? DEEP_TEAL : TEAL_700, borderRadius: 3 }} />
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Every piece of creative we captured</div>
            <div style={{ fontSize: 11, color: MUTED, margin: '3px 0 14px' }}>Tags are our read of the stage, the content type, and the caption itself.</div>
          </div>
          {(stageFilter || typeFilter) && (
            <div style={{ fontSize: 11, color: SLATE_600 }}>
              Showing {filtered.length} of {data.creatives.length}
              {stageFilter && <> · stage: <b>{stageFilter}</b></>}
              {typeFilter && <> · type: <b>{typeFilter}</b></>}
              {' '}<button onClick={() => { setStageFilter(null); setTypeFilter(null) }} style={{ background: 'none', border: 'none', color: TEAL_700, cursor: 'pointer', fontFamily: 'Poppins, sans-serif' }}>clear</button>
            </div>
          )}
        </div>
        {filtered.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 13 }}>
            {filtered.map((cr, i) => <CreativeCard key={i} cr={cr} big brand={brand} />)}
          </div>
        ) : <div style={{ fontSize: 12, color: MUTED, fontStyle: 'italic' }}>
          {data.creatives.length ? 'No creative matches this filter.' : 'Nothing captured on this channel yet.'}
        </div>}
      </div>
    </div>
  )
}

function Sparkline({ weeks, labels, height = 44 }) {
  const m = Math.max(...weeks, 1)
  return (
    <div>
      <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height, marginRight: 4, fontSize: 8.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>
          <span>{m}</span><span>0</span>
        </div>
        {weeks.map((w, i) => (
          <div key={i} title={`${labels?.[i] || ''}: ${w}`} style={{ flex: 1, height: Math.max(5, (w / m) * height), background: '#CFE9EC', borderRadius: '2px 2px 0 0' }} />
        ))}
      </div>
      {labels && (
        <div style={{ display: 'flex', gap: 4, marginTop: 3, marginLeft: 20 }}>
          {weeks.map((_, i) => (
            <div key={i} style={{ flex: 1, textAlign: 'center', fontSize: 7.5, color: MUTED, overflow: 'hidden', whiteSpace: 'nowrap' }}>
              {i % 3 === 0 ? labels[i] : ''}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
