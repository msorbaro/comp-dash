import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StageBar, MixCaption, ReadLine, CreativeCard, RowDivider, InfoLabel } from '../components/Widgets'
import {
  competesBadgeStyle, paidChipStyle, fmtNum, mixLabel, verdict,
  dominantIdx, dominantWord, STAGES, MUTED, INK_TEXT, SLATE_600, SLATE_400, SLATE_200, TEAL_700, DEEP_TEAL, INK, TRACK,
  METRIC_DEFINITIONS, engagementExplanation,
} from '../styles'

export default function Brand({ meta, brand, onBrandChange, onOpenChannel, onOpenCategory }) {
  const [profile, setProfile] = useState(null)
  const [channelCreatives, setChannelCreatives] = useState({})

  useEffect(() => {
    setProfile(null)
    api.brand(brand).then(setProfile)
  }, [brand])

  useEffect(() => {
    if (!profile) return
    profile.rows.forEach((r) => {
      if (r.total_all_time > 0) {
        api.channel(brand, r.channel.id, 4).then((d) =>
          setChannelCreatives((prev) => ({ ...prev, [r.channel.id]: d.creatives }))
        )
      }
    })
  }, [profile, brand])

  if (!profile) return <div style={{ padding: 40, color: MUTED }}>Loading…</div>

  const takeaway = `${brand} is ${verdict(profile.mix).toLowerCase()}. Its heaviest channel is ` +
    `${profile.rows.find((r) => r.channel.id === profile.lead_channel_id)?.channel.name}, and ` +
    `${profile.active_channels} of 7 channels are in active use` +
    (profile.consistency != null ? ` — message consistency across them scores ${profile.consistency}/100.` : '.')

  return (
    <div>
      <ContextBar
        scopeLabel="SCOPE · ONE BRAND"
        note="This view and its channel pages show only the brand in focus."
        brands={meta.brands}
        brandValue={brand}
        onBrandChange={onBrandChange}
      />
      <SectionNumber num="02" title="Brand Deep Dive" />

      <div style={{ background: INK, borderRadius: 13, padding: '24px 26px', color: '#FFFFFF', marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 30, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 330px', minWidth: 280 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 9 }}>
              <div style={{ fontSize: 9.5, letterSpacing: '.15em', color: '#22B8C4', fontWeight: 600 }}>{profile.category.toUpperCase()}</div>
              <div style={competesBadgeStyle(profile.category === 'Our Brands' ? 'portfolio' : 'direct', true)}>PORTFOLIO / COMPETITOR</div>
            </div>
            <h1 style={{ margin: 0, fontSize: 31, fontWeight: 600, letterSpacing: '-.022em' }}>{brand}</h1>
            <p style={{ margin: '10px 0 0', fontSize: 13, color: '#C7CED9', maxWidth: 620, lineHeight: 1.5 }}>{takeaway}</p>
          </div>
          <div style={{ display: 'flex', gap: 26, flex: 'none', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            {[
              ['TRACKED OUTPUT', fmtNum(profile.monthly_output), 'items / month', METRIC_DEFINITIONS.trackedOutput],
              ['ACTIVE CHANNELS', `${profile.active_channels}/7`, 'of channels tracked', METRIC_DEFINITIONS.activeChannels],
              ['CONSISTENCY', profile.consistency != null ? String(profile.consistency) : '—', 'same story across channels, 0-100', METRIC_DEFINITIONS.consistency],
            ].map(([lbl, val, note, def]) => (
              <div key={lbl}>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: SLATE_400, fontWeight: 600 }}>
                  <InfoLabel text={lbl} tooltip={def} />
                </div>
                <div style={{ fontSize: 23, fontWeight: 600, marginTop: 5 }}>{val}</div>
                <div style={{ fontSize: 10.5, color: SLATE_400 }}>{note}</div>
              </div>
            ))}
            <div style={{ width: 190 }}>
              <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: SLATE_400, fontWeight: 600, marginBottom: 8 }}>PORTFOLIO MIX</div>
              <StageBar mix={profile.mix} height={12} trackColor="rgba(255,255,255,.12)" />
              <MixCaption mix={profile.mix} color={SLATE_400} />
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          onClick={() => onOpenCategory(profile.category)}
          style={{ border: '1px solid #CBD5E1', background: '#FFFFFF', borderRadius: 7, padding: '8px 14px', fontSize: 11.5, fontWeight: 500, cursor: 'pointer', color: DEEP_TEAL, fontFamily: 'Poppins, sans-serif' }}
        >
          View {profile.category} rollup →
        </button>
      </div>

      <div style={{ fontSize: 14, fontWeight: 600 }}>Channel summary</div>
      <div style={{ fontSize: 11, color: MUTED, margin: '3px 0 14px' }}>
        Scale of use, See/Think/Do split, and the message being carried in each stage.
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1.1fr 1.4fr 2.4fr 0.9fr', gap: 14 }}>
        {[
          ['CHANNEL', null], ['TOTAL POSTED', 'All-time total for this channel, plus the long-run monthly average (total ÷ months tracked) - a channel gone quiet for 90+ days still shows its real history here instead of reading as zero.'],
          ['SEE / THINK / DO', null], ['WHAT IS SAID, BY STAGE', null], ['AVG. ENGAGEMENT', null],
        ].map(([label, tip]) => (
          <div key={label} style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600 }}>
            {tip ? <InfoLabel text={label} tooltip={tip} /> : label}
          </div>
        ))}
      </div>
      <hr style={{ margin: '6px 0 4px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
      {profile.rows.map((r, idx) => (
        <div key={r.channel.id}>
          <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1.1fr 1.4fr 2.4fr 0.9fr', gap: 14, padding: '13px 0', alignItems: 'start' }}>
            <div>
              <button
                onClick={() => onOpenChannel(r.channel.id)}
                style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 12, fontWeight: 600, color: INK_TEXT, fontFamily: 'Poppins, sans-serif' }}
              >
                {r.channel.name}
              </button>
              <div style={paidChipStyle(r.channel.paid)}>{r.channel.paid ? 'PAID' : 'OWNED / ORGANIC'}</div>
            </div>
            <div>
              <div style={{ fontSize: 17, fontWeight: 600 }}>{r.total_all_time}<span style={{ fontSize: 9.5, color: MUTED, fontWeight: 400 }}> total {r.channel.unit}</span></div>
              <div style={{ height: 5, borderRadius: 3, background: TRACK, marginTop: 6, overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${r.total_bar_pct}%`, background: DEEP_TEAL }} />
              </div>
              <div style={{ fontSize: 11, marginTop: 5, color: MUTED }}>
                ~{r.monthly_avg_all_time}/mo avg{r.last_posted ? ` · last posted ${r.last_posted}` : ''}
              </div>
            </div>
            <div>
              <StageBar mix={r.split} />
              <MixCaption mix={r.split} />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              {STAGES.map((s, i) => (
                <div key={s.id} style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <div style={{ width: 6, height: 6, borderRadius: 2, background: s.color, flex: 'none' }} />
                    <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: '.05em', color: SLATE_600 }}>{s.name.toUpperCase()} {r.split[i]}%</div>
                  </div>
                  {(r.messages[s.name] || []).length ? r.messages[s.name].map((m, j) => (
                    <div key={j} style={{ fontSize: 10, color: INK_TEXT, lineHeight: 1.35, marginTop: 3 }}>{m}</div>
                  )) : <div style={{ fontSize: 10, color: MUTED, fontStyle: 'italic', marginTop: 3 }}>no examples yet</div>}
                </div>
              ))}
            </div>
            <div style={{ textAlign: 'right' }} title={engagementExplanation(r.channel.id)}>
              <div style={{ fontSize: 15, fontWeight: 600, cursor: 'help' }}>{r.engagement != null ? fmtNum(r.engagement) : '—'}</div>
              <div style={{ fontSize: 9.5, color: MUTED }}>{r.share != null ? `${r.share}% of output (90d)` : ''}</div>
            </div>
          </div>
          {idx < profile.rows.length - 1 && <RowDivider />}
        </div>
      ))}

      {profile.rows.filter((r) => r.total_all_time > 0).map((r) => (
        <div key={r.channel.id} style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{r.channel.name}</h2>
                <div style={paidChipStyle(r.channel.paid)}>{r.channel.paid ? 'PAID' : 'OWNED / ORGANIC'}</div>
              </div>
              <div style={{ marginTop: 7, maxWidth: 500 }}>
                <ReadLine text={channelTakeaway(r)} />
              </div>
            </div>
            <div style={{ width: 160 }}>
              <StageBar mix={r.split} />
              <MixCaption mix={r.split} />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '230px 1fr', gap: 22 }}>
            <div>
              <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, marginBottom: 10 }}>CONTENT TYPES</div>
              {r.content_types.length ? r.content_types.slice(0, 5).map((ct) => (
                <div key={ct.name} style={{ marginBottom: 8 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, marginBottom: 3 }}>
                    <span>{ct.name}</span><span style={{ color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{ct.pct}%</span>
                  </div>
                  <div style={{ height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${ct.pct}%`, background: TEAL_700, borderRadius: 3 }} />
                  </div>
                </div>
              )) : <div style={{ fontSize: 11, color: MUTED, fontStyle: 'italic' }}>Not enough classified content yet.</div>}
              <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, margin: '14px 0 6px' }}>CADENCE · 12 WEEKS</div>
              <Sparkline weeks={r.weeks} />
            </div>
            <div>
              <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, marginBottom: 10 }}>CREATIVE EVIDENCE</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 11 }}>
                {(channelCreatives[r.channel.id] || []).map((cr, i) => <CreativeCard key={i} cr={cr} />)}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function channelTakeaway(r) {
  const topCt = r.content_types.length ? [...r.content_types].sort((a, b) => b.pct - a.pct)[0].name.toLowerCase() : 'unclassified content'
  const idx = dominantIdx(r.split)
  return `${r.split[idx]}% ${dominantWord(r.split).replace('-led', '')}. Led by ${topCt} ` +
    `(${r.total_all_time} tracked, ~${r.monthly_avg_all_time}/mo).`
}

function Sparkline({ weeks }) {
  const m = Math.max(...weeks, 1)
  return (
    <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end', height: 44 }}>
      {weeks.map((w, i) => (
        <div key={i} style={{ flex: 1, height: Math.max(4, (w / m) * 44), background: '#CFE9EC', borderRadius: '2px 2px 0 0' }} />
      ))}
    </div>
  )
}
