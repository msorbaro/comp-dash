import { useState } from 'react'
import {
  STAGES, TRACK, MUTED, MONO, INK_TEXT, SLATE_600, DEEP_TEAL, TEAL, TEAL_WASH,
  SLATE_200, SURFACE, MEDIA_HEIGHT, fmtNum, mixLabel,
} from '../styles'

export function StageBar({ mix, height = 11, radius = 6, trackColor = TRACK }) {
  return (
    <div style={{ display: 'flex', height, borderRadius: radius, overflow: 'hidden', background: trackColor }}>
      {STAGES.map((s, i) => (
        <div key={s.id} style={{ width: `${Math.max(mix[i], 0)}%`, background: s.color }} />
      ))}
    </div>
  )
}

export function MixCaption({ mix, suffix = 'see/think/do', color = MUTED }) {
  return (
    <div style={{ fontSize: 10.5, color, marginTop: 7, fontFamily: MONO }}>
      {mixLabel(mix)}{suffix ? `  ${suffix}` : ''}
    </div>
  )
}

export function StatCard({ label, value, note, valueColor = DEEP_TEAL }) {
  return (
    <div style={{ background: SURFACE, border: `1px solid ${SLATE_200}`, borderRadius: 10, padding: '15px 16px' }}>
      <div style={{ fontSize: 9.5, letterSpacing: '.13em', color: MUTED, fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 26, fontWeight: 600, letterSpacing: '-.02em', margin: '6px 0 2px', color: valueColor }}>{value}</div>
      <div style={{ fontSize: 11, color: SLATE_600, lineHeight: 1.4 }}>{note}</div>
    </div>
  )
}

export function Legend({ dotShape = 'square' }) {
  return (
    <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
      {STAGES.map((s) => (
        <div key={s.id} style={{ display: 'flex', gap: 7, alignItems: 'flex-start', width: 150 }}>
          <div style={{ width: 9, height: 9, borderRadius: dotShape === 'square' ? 2 : '50%', background: s.color, marginTop: 3, flex: 'none' }} />
          <div>
            <div style={{ fontSize: 11, fontWeight: 600 }}>{s.name}</div>
            <div style={{ fontSize: 10, color: MUTED, lineHeight: 1.35 }}>{s.desc}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

export function ReadLine({ text }) {
  return (
    <div style={{ fontSize: 12.5, lineHeight: 1.5, padding: '13px 15px', background: TEAL_WASH, borderRadius: 9, borderLeft: `3px solid ${TEAL}` }}>
      <span style={{ fontWeight: 600, color: DEEP_TEAL }}>Read: </span>{text}
    </div>
  )
}

export function ScopeChip({ label }) {
  return (
    <div style={{ fontSize: 9.5, letterSpacing: '.13em', fontWeight: 600, color: DEEP_TEAL, background: TEAL_WASH, border: '1px solid #CFE9EC', borderRadius: 5, padding: '5px 9px', whiteSpace: 'nowrap', display: 'inline-block' }}>
      {label}
    </div>
  )
}

export function SectionNumber({ num, title }) {
  return (
    <div style={{ fontSize: 11, letterSpacing: '.15em', color: MUTED, fontWeight: 600, margin: '18px 0 10px' }}>
      {num} · {title.toUpperCase()}
    </div>
  )
}

export function RowDivider() {
  return <div style={{ height: 1, background: '#F1F5F9', margin: '13px 0' }} />
}

export function TableHead({ columns }) {
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: columns.map((c) => c.width || '1fr').join(' '), gap: 14 }}>
        {columns.map((c) => (
          <div key={c.label} style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600 }}>{c.label}</div>
        ))}
      </div>
      <hr style={{ margin: '6px 0 4px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
    </>
  )
}

export function CreativeCard({ cr, big = false }) {
  const [playing, setPlaying] = useState(false)
  const stageColor = STAGES.find((s) => s.name === cr.stage)?.color || MUTED
  const mediaH = MEDIA_HEIGHT[cr.shape] || 104
  return (
    <div style={{ border: `1px solid ${SLATE_200}`, borderRadius: 10, overflow: 'hidden', background: '#FBFCFD' }}>
      <div style={{ position: 'relative', height: mediaH, display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: `1px solid ${SLATE_200}`, background: cr.image ? undefined : 'repeating-linear-gradient(135deg,#EEF2F6 0 7px,#E4EAF1 7px 14px)' }}>
        {cr.image ? (
          <img src={cr.image} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
        ) : (
          <div style={{ fontFamily: MONO, fontSize: 9.5, color: '#5A6773', textAlign: 'center', padding: '0 10px', lineHeight: 1.4 }}>
            {cr.why || cr.type || 'no preview'}
          </div>
        )}
        {cr.stage && (
          <div style={{ position: 'absolute', left: 8, top: 8, fontSize: 8.5, fontWeight: 600, letterSpacing: '.1em', color: '#FFFFFF', background: stageColor, borderRadius: 4, padding: '2px 6px' }}>
            {cr.stage}
          </div>
        )}
      </div>
      <div style={{ padding: big ? '12px 13px 13px' : '10px 11px 11px' }}>
        <div style={{ display: 'inline-block', fontSize: 9.5, fontWeight: 600, letterSpacing: '.06em', color: SLATE_600, background: '#F1F5F9', borderRadius: 4, padding: '3px 7px' }}>
          {cr.type || '—'}
        </div>
        <div style={{ fontSize: big ? 11 : 10.5, color: INK_TEXT, lineHeight: 1.4, marginTop: 7 }}>{cr.why}</div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 9, fontSize: 9.5, color: MUTED, fontFamily: MONO }}>
          <span>{cr.engagement != null ? `${fmtNum(cr.engagement)} eng.` : '—'}</span>
          <span>{cr.date}</span>
        </div>
        {(cr.video_url || cr.embed_html) && (
          <div style={{ marginTop: 8 }}>
            {!playing ? (
              <button
                onClick={() => setPlaying(true)}
                style={{ background: 'none', border: 'none', padding: 0, fontSize: 10.5, color: DEEP_TEAL, cursor: 'pointer', fontFamily: 'Poppins, sans-serif' }}
              >
                ▶ Play
              </button>
            ) : (
              <>
                {cr.video_url && <video controls autoPlay src={cr.video_url} style={{ width: '100%', marginTop: 6, borderRadius: 6 }} />}
                {cr.embed_html && (
                  <iframe
                    title="tiktok"
                    src={`https://www.tiktok.com/embed/v2/${cr.embed_html}`}
                    style={{ width: '100%', height: 500, border: 'none', marginTop: 6 }}
                    allow="encrypted-media;"
                  />
                )}
              </>
            )}
          </div>
        )}
        {cr.link && (
          <a href={cr.link} target="_blank" rel="noreferrer" style={{ display: 'block', textAlign: 'center', marginTop: 8, fontSize: 10.5, fontWeight: 600, color: DEEP_TEAL, border: `1px solid ${SLATE_200}`, borderRadius: 6, padding: '5px 0' }}>
            Open
          </a>
        )}
      </div>
    </div>
  )
}
