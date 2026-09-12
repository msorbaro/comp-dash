import { useEffect, useState } from 'react'
import { api } from '../api'
import { SectionNumber, StageBar, MixCaption, ReadLine, CreativeCard } from '../components/Widgets'
import {
  paidChipStyle, trendColor, trendLabel, fmtNum, dominantIdx, dominantWord,
  STAGES, MUTED, INK_TEXT, SLATE_600, SLATE_200, TEAL_700, TRACK,
} from '../styles'

export default function Channel({ brand, category, channelId, onBack }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    api.channel(brand, channelId, 8).then(setData)
  }, [brand, channelId])

  if (!data) return <div style={{ padding: 40, color: MUTED }}>Loading…</div>
  const r = data.channel_data
  const ch = r.channel
  const topCt = r.content_types.length ? [...r.content_types].sort((a, b) => b.pct - a.pct)[0].name.toLowerCase() : 'unclassified content'
  const idx = dominantIdx(r.split)
  const takeaway = `${r.split[idx]}% ${dominantWord(r.split).replace('-led', '')}. Led by ${topCt} (${r.volume} in the last 90 days).`

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
          <div style={{ fontSize: 12, color: SLATE_600, marginTop: 6 }}>{brand} · {category} · last 90 days</div>
          <div style={{ marginTop: 14 }}><ReadLine text={takeaway} /></div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 14, marginTop: 20 }}>
            {STAGES.map((s, i) => (
              <div key={s.id} style={{ background: '#FAFBFC', border: `1px solid ${SLATE_200}`, borderTop: `3px solid ${s.color}`, borderRadius: 10, padding: '14px 15px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: '.1em', color: SLATE_600 }}>{s.name.toUpperCase()}</div>
                  <div style={{ fontSize: 22, fontWeight: 600, color: s.color }}>{r.split[i]}%</div>
                </div>
                <div style={{ marginTop: 11, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {(r.messages[s.name] || []).length ? r.messages[s.name].map((m, j) => (
                    <div key={j} style={{ fontSize: 11, color: INK_TEXT, lineHeight: 1.4, padding: '7px 9px', background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 7 }}>{m}</div>
                  )) : <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>no examples yet</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '18px 19px' }}>
            <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>SCALE OF USE</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginTop: 6 }}>
              <div style={{ fontSize: 30, fontWeight: 600 }}>{r.volume}</div><div style={{ fontSize: 11, color: MUTED }}>{ch.unit}</div>
            </div>
            <div style={{ fontSize: 11, marginTop: 4, color: trendColor(r.trend) }}>{trendLabel(r.trend)}</div>
            <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, margin: '18px 0 9px' }}>CADENCE · 12 WEEKS</div>
            <Sparkline weeks={r.weeks} height={56} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 18 }}>
              <div>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>AVG. ENGAGEMENT</div>
                <div style={{ fontSize: 19, fontWeight: 600, marginTop: 4 }}>{r.engagement != null ? fmtNum(r.engagement) : '—'}</div>
              </div>
              <div>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>SHARE OF OUTPUT</div>
                <div style={{ fontSize: 19, fontWeight: 600, marginTop: 4 }}>{r.share != null ? `${r.share}%` : '—'}</div>
              </div>
            </div>
          </div>
          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '18px 19px' }}>
            <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, marginBottom: 11 }}>CONTENT TYPES</div>
            {r.content_types.slice(0, 5).map((ct) => (
              <div key={ct.name} style={{ marginBottom: 9 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span>{ct.name}</span><span style={{ color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{ct.pct}%</span>
                </div>
                <div style={{ height: 6, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${ct.pct}%`, background: TEAL_700, borderRadius: 3 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px' }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>Every piece of creative we captured</div>
        <div style={{ fontSize: 11, color: MUTED, margin: '3px 0 14px' }}>Tags are our read of the stage, the content type, and the caption itself.</div>
        {data.creatives.length ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 13 }}>
            {data.creatives.map((cr, i) => <CreativeCard key={i} cr={cr} big />)}
          </div>
        ) : <div style={{ fontSize: 12, color: MUTED, fontStyle: 'italic' }}>Nothing captured on this channel yet.</div>}
      </div>
    </div>
  )
}

function Sparkline({ weeks, height = 44 }) {
  const m = Math.max(...weeks, 1)
  return (
    <div style={{ display: 'flex', gap: 4, alignItems: 'flex-end', height }}>
      {weeks.map((w, i) => (
        <div key={i} style={{ flex: 1, height: Math.max(5, (w / m) * height), background: '#CFE9EC', borderRadius: '2px 2px 0 0' }} />
      ))}
    </div>
  )
}
