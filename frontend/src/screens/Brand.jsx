import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StageBar, MixCaption, ReadLine, CreativeCard, RowDivider, InfoLabel } from '../components/Widgets'
import {
  competesBadgeStyle, paidChipStyle, fmtNum, mixLabel, verdict,
  dominantIdx, dominantWord, STAGES, MUTED, INK_TEXT, SLATE_600, SLATE_400, SLATE_200, TEAL_700, DEEP_TEAL, INK, TRACK,
  METRIC_DEFINITIONS, engagementUnitLabel,
} from '../styles'

const SECTION_CREATIVE_FETCH_N = 16 // headroom so a content-type click still has real results

export default function Brand({ meta, brand, onBrandChange, onOpenChannel, onOpenCategory }) {
  const [profile, setProfile] = useState(null)
  const [error, setError] = useState(null)
  const [channelCreatives, setChannelCreatives] = useState({})
  const [typeFilters, setTypeFilters] = useState({})
  const [filteredCreatives, setFilteredCreatives] = useState({})

  const load = () => {
    setProfile(null)
    setError(null)
    setChannelCreatives({})
    setTypeFilters({})
    setFilteredCreatives({})
    api.brand(brand).then(setProfile).catch((e) => setError(e.message))
  }
  useEffect(load, [brand])

  useEffect(() => {
    if (!profile) return
    profile.rows.forEach((r) => {
      if (r.total_all_time > 0) {
        api.channel(brand, r.channel.id, SECTION_CREATIVE_FETCH_N).then((d) =>
          setChannelCreatives((prev) => ({ ...prev, [r.channel.id]: d.creatives }))
        )
      }
    })
  }, [profile, brand])

  // Filtering a content type re-fetches from the server for that specific
  // type instead of filtering the small unfiltered preview batch client-side
  // - a less-common type frequently doesn't appear at all in the first
  // SECTION_CREATIVE_FETCH_N most-recent items, which made the filter look
  // like it was clearing every tile instead of showing matching ones.
  const toggleTypeFilter = (channelId, typeName) => {
    const isActive = typeFilters[channelId] === typeName
    const next = isActive ? null : typeName
    setTypeFilters((prev) => ({ ...prev, [channelId]: next }))
    if (next) {
      setFilteredCreatives((prev) => ({ ...prev, [channelId]: null })) // null = loading
      api.channel(brand, channelId, 8, next).then((d) =>
        setFilteredCreatives((prev) => ({ ...prev, [channelId]: d.creatives }))
      )
    }
  }

  if (error) return (
    <div style={{ padding: 40, color: MUTED }}>
      Couldn't load this brand ({error}).{' '}
      <span onClick={load} style={{ textDecoration: 'underline', cursor: 'pointer' }}>Try again</span>
    </div>
  )
  if (!profile) return <div style={{ padding: 40, color: MUTED }}>Loading…</div>

  // Channel summary order: currently-active channels first, dormant ones
  // (real history, but nothing in over a year) below those, and channels
  // with no history at all last - a channel that's simply never been used
  // shouldn't sit above one that's actively running just because of list
  // position.
  const rowRank = (r) => (r.total_all_time === 0 ? 2 : r.stale ? 1 : 0)
  const summaryRows = [...profile.rows].sort((a, b) => rowRank(a) - rowRank(b))

  const leadRow = profile.rows.find((r) => r.channel.id === profile.lead_channel_id)
  const leadEngLabel = leadRow ? engagementUnitLabel(leadRow.channel.id) : ''
  const leadEngClause = leadRow?.recent_engagement != null && !['not tracked', 'n/a'].includes(leadEngLabel)
    ? `, averaging ${fmtNum(leadRow.recent_engagement)} ${leadEngLabel} recently`
    : ''
  const takeaway = `${brand} is ${verdict(profile.mix).toLowerCase()}. ` +
    (profile.lead_is_recent
      ? `Its most active channel right now is ${leadRow?.channel.name} — ${leadRow?.volume} ${leadRow?.channel.unit} in the last 90 days${leadEngClause} — and `
      : `No channel has meaningful volume in the last 90 days — historically its highest-volume channel was ${leadRow?.channel.name}, and `) +
    `${profile.active_channels} of 7 channels are in active use.`

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
            {profile.tagline && (
              <div style={{ fontSize: 13, fontStyle: 'italic', color: '#22B8C4', marginTop: 4 }}>
                &ldquo;{profile.tagline}&rdquo;
              </div>
            )}
            <p style={{ margin: '10px 0 0', fontSize: 13, color: '#C7CED9', maxWidth: 620, lineHeight: 1.5 }}>{takeaway}</p>
            {profile.positioning && (
              <p style={{ margin: '8px 0 0', fontSize: 12, color: '#94A3B8', maxWidth: 620, lineHeight: 1.5 }} title="AI-synthesized from only this brand's content captured in the last 6 months - a starting read, not a verified brand statement.">
                <b style={{ color: '#C7CED9' }}>Last 6M Positioning:</b> {profile.positioning}
              </p>
            )}
          </div>
          <div style={{ display: 'flex', gap: 22, flex: 'none', alignItems: 'flex-start', flexWrap: 'wrap' }}>
            {[
              ['TRACKED OUTPUT', fmtNum(profile.monthly_output) + ' /mo', METRIC_DEFINITIONS.trackedOutput],
              ['ACTIVE CHANNELS', `${profile.active_channels}/7`, METRIC_DEFINITIONS.activeChannels],
            ].map(([lbl, val, def]) => (
              <div key={lbl} style={{ width: 148 }}>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: SLATE_400, fontWeight: 600 }}>
                  <InfoLabel text={lbl} tooltip={def} />
                </div>
                <div style={{ fontSize: 23, fontWeight: 600, marginTop: 5 }}>{val}</div>
                <div style={{ fontSize: 10, color: SLATE_400, lineHeight: 1.4, marginTop: 2 }}>{def}</div>
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
      {summaryRows.map((r, idx) => {
        const neverActive = r.total_all_time === 0
        const deemphasized = r.stale || neverActive
        return (
        <div key={r.channel.id}>
          {r.stale && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10.5, fontWeight: 600, color: '#B45309', background: '#FFFBEB', border: '1px solid #FDE9C8', borderRadius: 6, padding: '5px 9px', margin: '10px 0 0', width: 'fit-content' }}>
              ⚠ DORMANT — no activity in over a year (last posted {r.last_posted})
            </div>
          )}
          {neverActive && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10.5, fontWeight: 600, color: SLATE_600, background: '#F1F5F9', border: `1px solid ${SLATE_200}`, borderRadius: 6, padding: '5px 9px', margin: '10px 0 0', width: 'fit-content' }}>
              NEVER ACTIVE — no {r.channel.unit} captured for this brand, ever
            </div>
          )}
          <div style={{ display: 'grid', gridTemplateColumns: '1.3fr 1.1fr 1.4fr 2.4fr 0.9fr', gap: 14, padding: '13px 0', alignItems: 'start', opacity: deemphasized ? 0.5 : 1 }}>
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
              <div style={{ fontSize: 11, marginTop: 4, color: MUTED }}>
                {neverActive
                  ? 'No activity ever captured for this channel'
                  : r.stale
                    ? `Historically active, but nothing posted since ${r.last_posted}`
                    : `~${r.monthly_avg_all_time}/mo avg${r.last_posted ? ` · last posted ${r.last_posted}` : ''}`}
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
                  <div style={{ fontSize: 10, color: INK_TEXT, lineHeight: 1.35, marginTop: 3 }}>
                    {r.stage_summaries?.[s.name] || (r.total_all_time > 0
                      ? <span style={{ color: MUTED, fontStyle: 'italic' }}>summarizing…</span>
                      : <span style={{ color: MUTED, fontStyle: 'italic' }}>no examples yet</span>)}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{r.engagement != null ? fmtNum(r.engagement) : '—'}</div>
              <div style={{ fontSize: 9.5, color: MUTED }}>{engagementUnitLabel(r.channel.id)}</div>
            </div>
          </div>
          {idx < summaryRows.length - 1 && <RowDivider />}
        </div>
        )
      })}

      {profile.rows.filter((r) => r.total_all_time > 0).map((r) => (
        <div key={r.channel.id} style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 24, marginBottom: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600 }}>{r.channel.name}</h2>
                <div style={paidChipStyle(r.channel.paid)}>{r.channel.paid ? 'PAID' : 'OWNED / ORGANIC'}</div>
                {r.stale && (
                  <div style={{ fontSize: 8.5, fontWeight: 600, letterSpacing: '.08em', color: '#B45309', background: '#FFFBEB', border: '1px solid #FDE9C8', borderRadius: 4, padding: '3px 7px' }}>
                    DORMANT · SINCE {r.last_posted?.toUpperCase()}
                  </div>
                )}
              </div>
              <div style={{ marginTop: 7, maxWidth: 500 }}>
                <ReadLine text={r.read_line || channelTakeaway(r)} />
              </div>
            </div>
            <div style={{ width: 160 }}>
              <StageBar mix={r.split} />
              <MixCaption mix={r.split} />
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '230px 1fr', gap: 22 }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>CONTENT TYPES</div>
                {typeFilters[r.channel.id] && (
                  <button
                    onClick={() => toggleTypeFilter(r.channel.id, typeFilters[r.channel.id])}
                    style={{ background: 'none', border: 'none', color: TEAL_700, fontSize: 10, cursor: 'pointer', fontFamily: 'Poppins, sans-serif' }}
                  >
                    clear
                  </button>
                )}
              </div>
              {r.content_types.length ? r.content_types.slice(0, 5).map((ct) => {
                const active = typeFilters[r.channel.id] === ct.name
                return (
                  <div key={ct.name} style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <button
                        onClick={() => toggleTypeFilter(r.channel.id, ct.name)}
                        style={{ flex: 1, minWidth: 0, textAlign: 'left', background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontFamily: 'Poppins, sans-serif' }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10.5, marginBottom: 3, color: active ? DEEP_TEAL : INK_TEXT, fontWeight: active ? 600 : 400 }}>
                          <span>{ct.name}</span><span style={{ color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{ct.pct}%</span>
                        </div>
                        <div style={{ height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${ct.pct}%`, background: active ? DEEP_TEAL : TEAL_700, borderRadius: 3 }} />
                        </div>
                      </button>
                      <button
                        onClick={() => onOpenChannel(r.channel.id, ct.name)}
                        title={`See every ${ct.name} execution on ${r.channel.name}`}
                        style={{ flex: 'none', background: 'none', border: 'none', color: TEAL_700, fontSize: 9.5, cursor: 'pointer', fontFamily: 'Poppins, sans-serif', whiteSpace: 'nowrap' }}
                      >
                        See all →
                      </button>
                    </div>
                  </div>
                )
              }) : <div style={{ fontSize: 11, color: MUTED, fontStyle: 'italic' }}>Not enough classified content yet.</div>}
              <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, margin: '14px 0 2px' }}>CADENCE · 12 WEEKS</div>
              <div style={{ fontSize: 9, color: MUTED, marginBottom: 6 }}>Y: {r.channel.unit} per week · X: week-starting date</div>
              <Sparkline weeks={r.weeks} labels={r.week_labels} />
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>
                  CREATIVE EVIDENCE{typeFilters[r.channel.id] ? ` · ${typeFilters[r.channel.id]}` : ''}
                </div>
                <button
                  onClick={() => onOpenChannel(r.channel.id, typeFilters[r.channel.id] || null)}
                  style={{ background: 'none', border: 'none', color: TEAL_700, fontSize: 10, cursor: 'pointer', fontFamily: 'Poppins, sans-serif' }}
                >
                  See all {r.total_all_time} →
                </button>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 11 }}>
                {typeFilters[r.channel.id] ? (
                  filteredCreatives[r.channel.id] === null || filteredCreatives[r.channel.id] === undefined ? (
                    <div style={{ fontSize: 11, color: MUTED, fontStyle: 'italic', gridColumn: '1 / -1' }}>Loading…</div>
                  ) : filteredCreatives[r.channel.id].length ? (
                    filteredCreatives[r.channel.id].slice(0, 8).map((cr, i) => <CreativeCard key={i} cr={cr} brand={brand} />)
                  ) : (
                    <div style={{ fontSize: 11, color: MUTED, fontStyle: 'italic', gridColumn: '1 / -1' }}>No captured creative matches this type.</div>
                  )
                ) : (
                  (channelCreatives[r.channel.id] || []).slice(0, 8).map((cr, i) => <CreativeCard key={i} cr={cr} brand={brand} />)
                )}
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

function Sparkline({ weeks, labels, height = 44 }) {
  const m = Math.max(...weeks, 1)
  return (
    <div>
      <div style={{ display: 'flex', gap: 3, alignItems: 'flex-end', height }}>
        <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', height, marginRight: 4, fontSize: 8.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>
          <span>{m}</span><span>0</span>
        </div>
        {weeks.map((w, i) => (
          <div key={i} title={`${labels?.[i] || ''}: ${w}`} style={{ flex: 1, height: Math.max(4, (w / m) * height), background: '#CFE9EC', borderRadius: '2px 2px 0 0' }} />
        ))}
      </div>
      {labels && (
        <div style={{ display: 'flex', gap: 3, marginTop: 3, marginLeft: 20 }}>
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
