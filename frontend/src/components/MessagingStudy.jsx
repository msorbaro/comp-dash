import { useEffect, useState } from 'react'
import { api } from '../api'
import { SectionNumber, StageBar, PageSkeleton, RowDivider, TableHead } from './Widgets'
import {
  MUTED, INK_TEXT, SLATE_200, SLATE_600, SLATE_400, DEEP_TEAL, TEAL, TEAL_700, TEAL_WASH, AMBER,
  ROSE, GREEN, TRACK, MONO, fmtNum, mixLabel,
  ATTRIBUTE_ORDER, ATTRIBUTE_SHORT, ATTRIBUTE_COLORS, CHANNEL_NAME, heatColor, heatTextColor,
} from '../styles'

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

function cardStyle() {
  return { background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }
}

function SoWhat({ children }) {
  return (
    <div style={{ fontSize: 12.5, lineHeight: 1.55, padding: '13px 15px', background: TEAL_WASH, borderRadius: 9, borderLeft: `3px solid ${TEAL}`, marginTop: 14 }}>
      <span style={{ fontWeight: 600, color: DEEP_TEAL }}>So what: </span>{children}
    </div>
  )
}

function SubHead({ title, note }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>{title}</div>
      {note && <div style={{ fontSize: 11, color: MUTED, marginTop: 3, lineHeight: 1.45, maxWidth: '70ch' }}>{note}</div>}
    </div>
  )
}

// ---------- Matrix 01 - territory heatmap ----------

function Heatmap({ data, onOpenBrand }) {
  const [scope, setScope] = useState('core')
  const rows = data.heatmap[scope]
  return (
    <div style={cardStyle()}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
        <SubHead
          title="Messaging territory by brand"
          note="Share of each brand's own classified output that lands in each territory. Darker means the brand leans harder on that claim."
        />
        <div style={{ display: 'flex', gap: 5, flex: 'none' }}>
          <button onClick={() => setScope('core')} style={pillStyle(scope === 'core')}>Portfolio + direct</button>
          <button onClick={() => setScope('all')} style={pillStyle(scope === 'all')}>All tracked brands</button>
        </div>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <div style={{ minWidth: 780 }}>
          <div style={{ display: 'grid', gridTemplateColumns: `170px repeat(${ATTRIBUTE_ORDER.length}, 1fr)`, gap: 3 }}>
            <div />
            {ATTRIBUTE_ORDER.map((a) => (
              <div key={a} title={a} style={{ fontSize: 9, fontWeight: 600, color: MUTED, textAlign: 'center', paddingBottom: 6 }}>
                {ATTRIBUTE_SHORT[a]}
              </div>
            ))}
          </div>
          {rows.map((r) => (
            <div key={r.company} style={{ display: 'grid', gridTemplateColumns: `170px repeat(${ATTRIBUTE_ORDER.length}, 1fr)`, gap: 3, marginBottom: 3 }}>
              <button
                onClick={() => onOpenBrand(r.company)}
                title={`${r.n} classified items`}
                style={{
                  background: 'none', border: 'none', padding: 0, cursor: 'pointer', textAlign: 'left', fontFamily: 'Poppins, sans-serif',
                  fontSize: 11, fontWeight: r.category === 'Our Brands' ? 600 : 500, color: r.category === 'Our Brands' ? DEEP_TEAL : INK_TEXT,
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}
              >
                {r.company}
              </button>
              {ATTRIBUTE_ORDER.map((a) => {
                const pct = r.attr[a] || 0
                return (
                  <div
                    key={a}
                    title={`${r.company} · ${a}: ${pct}%`}
                    style={{
                      background: heatColor(pct), color: heatTextColor(pct), borderRadius: 3,
                      fontFamily: MONO, fontSize: 9.5, textAlign: 'center', padding: '5px 0',
                    }}
                  >
                    {pct > 0 ? pct : ''}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---------- Matrix 02 - gap map ----------

function DivergingBars({ gap }) {
  const max = Math.max(...gap.map((g) => Math.abs(g.delta_vs_afs)), 1)
  return (
    <div>
      {gap.map((g) => {
        const widthPct = (Math.abs(g.delta_vs_afs) / max) * 50
        const positive = g.delta_vs_afs >= 0
        return (
          <div key={g.attribute} style={{ display: 'grid', gridTemplateColumns: '150px 1fr 62px', gap: 10, alignItems: 'center', padding: '5px 0' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: INK_TEXT, textAlign: 'right' }}>{ATTRIBUTE_SHORT[g.attribute]}</div>
            <div style={{ position: 'relative', height: 20, background: TRACK, borderRadius: 4 }}>
              <div style={{ position: 'absolute', left: '50%', top: -3, bottom: -3, width: 1, background: SLATE_400 }} />
              <div
                title={`Portfolio ${g.own}% vs direct competitors ${g.afs}%`}
                style={{
                  position: 'absolute', top: 3, bottom: 3, borderRadius: 3,
                  background: positive ? GREEN : ROSE,
                  ...(positive ? { left: '50%', width: `${widthPct}%` } : { right: '50%', width: `${widthPct}%` }),
                }}
              />
            </div>
            <div style={{ fontFamily: MONO, fontSize: 11.5, color: positive ? GREEN : ROSE, fontWeight: 600 }}>
              {positive ? '+' : ''}{g.delta_vs_afs}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function GapTable({ gap }) {
  const cols = [
    { label: 'TERRITORY', width: '140px' }, { label: 'PORTFOLIO' }, { label: 'DIRECT' },
    { label: 'ADJACENT' }, { label: 'BEST-IN-CLASS' }, { label: 'LOW-INTEREST' }, { label: 'BIG BOX' },
  ]
  return (
    <div>
      <TableHead columns={cols} />
      {gap.map((g, i) => (
        <div key={g.attribute}>
          <div style={{ display: 'grid', gridTemplateColumns: cols.map((c) => c.width || '1fr').join(' '), gap: 14, padding: '7px 0', fontSize: 11.5 }}>
            <div style={{ fontWeight: 600, color: INK_TEXT }}>{ATTRIBUTE_SHORT[g.attribute]}</div>
            <div style={{ fontFamily: MONO }}>{g.own}%</div>
            <div style={{ fontFamily: MONO }}>{g.afs}%</div>
            <div style={{ fontFamily: MONO }}>{g.adj}%</div>
            <div style={{ fontFamily: MONO }}>{g.bic}%</div>
            <div style={{ fontFamily: MONO }}>{g.lowint}%</div>
            <div style={{ fontFamily: MONO }}>{g.bigbox}%</div>
          </div>
          {i < gap.length - 1 && <RowDivider />}
        </div>
      ))}
    </div>
  )
}

// ---------- Matrix 03 - funnel posture ----------

function FunnelPosture({ rows }) {
  return (
    <div>
      {rows.map((r) => (
        <div key={r.company} style={{ display: 'grid', gridTemplateColumns: '210px 1fr 130px', gap: 12, alignItems: 'center', padding: '6px 0' }}>
          <div style={{ fontSize: 11.5, fontWeight: r.own ? 600 : 500, color: r.own ? DEEP_TEAL : INK_TEXT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {r.company}
          </div>
          <StageBar mix={[r.See, r.Think, r.Do]} height={14} />
          <div style={{ fontFamily: MONO, fontSize: 10, color: MUTED, textAlign: 'right' }}>{mixLabel([r.See, r.Think, r.Do])} · n={r.n}</div>
        </div>
      ))}
    </div>
  )
}

// ---------- Matrix 04 - channel x territory ----------

function TwoSidedAttrRows({ own, bic }) {
  const attrs = ATTRIBUTE_ORDER.filter((a) => a !== 'None Clear / Other' && ((own.attr[a] || 0) > 0 || (bic.attr[a] || 0) > 0))
    .sort((a, b) => (own.attr[b] || 0) - (own.attr[a] || 0)).slice(0, 4)
  if (!attrs.length) return <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>Not enough classified content yet.</div>
  return (
    <div>
      {attrs.map((a) => (
        <div key={a} style={{ marginBottom: 6 }}>
          <div style={{ fontSize: 10, color: INK_TEXT, marginBottom: 3 }}>{ATTRIBUTE_SHORT[a]}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
            <div style={{ flex: 1, height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${own.attr[a] || 0}%`, background: DEEP_TEAL, borderRadius: 3 }} />
            </div>
            <div style={{ width: 40, fontSize: 9, color: MUTED, fontFamily: MONO }}>{own.attr[a] || 0}%</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <div style={{ flex: 1, height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${bic.attr[a] || 0}%`, background: SLATE_400, borderRadius: 3 }} />
            </div>
            <div style={{ width: 40, fontSize: 9, color: MUTED, fontFamily: MONO }}>{bic.attr[a] || 0}%</div>
          </div>
        </div>
      ))}
    </div>
  )
}

function ChannelTerritory({ rows }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 16 }}>
      {rows.filter((r) => r.own.n > 0 || r.bic.n > 0).map((r) => (
        <div key={r.channel.id} style={{ border: `1px solid ${SLATE_200}`, borderRadius: 10, padding: '13px 14px' }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, marginBottom: 2 }}>{r.channel.name}</div>
          <div style={{ fontSize: 9.5, color: MUTED, marginBottom: 10, fontFamily: MONO }}>
            <span style={{ color: DEEP_TEAL }}>■</span> portfolio (n={r.own.n}) &nbsp;
            <span style={{ color: SLATE_400 }}>■</span> best-in-class (n={r.bic.n})
          </div>
          <TwoSidedAttrRows own={r.own} bic={r.bic} />
        </div>
      ))}
    </div>
  )
}

// ---------- Matrix 05 - content mix ----------

function ContentMix({ rows }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))', gap: 16 }}>
      {rows.filter((r) => r.total > 0).map((r) => {
        const top = Object.entries(r.pct).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 4)
        return (
          <div key={r.company} style={{ border: `1px solid ${SLATE_200}`, borderRadius: 10, padding: '13px 14px' }}>
            <div style={{ fontSize: 11.5, fontWeight: r.own ? 600 : 500, color: r.own ? DEEP_TEAL : INK_TEXT, marginBottom: 9 }}>{r.company}</div>
            {top.map(([cat, pct]) => (
              <div key={cat} title={cat} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <div style={{ width: 100, fontSize: 9.5, color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 'none' }}>{cat}</div>
                <div style={{ flex: 1, height: 9, background: TRACK, borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${pct}%`, background: TEAL_700, borderRadius: 4 }} />
                </div>
                <div style={{ width: 34, fontSize: 9.5, color: MUTED, fontFamily: MONO, flex: 'none' }}>{pct}%</div>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

// ---------- Matrix 06 - homepage leads ----------

function HomepageLeads({ rows }) {
  const cols = [{ label: 'BRAND', width: '220px' }, { label: 'HOMEPAGE LEADS WITH' }, { label: 'CAPTURED', width: '110px' }]
  return (
    <div>
      <TableHead columns={cols} />
      {rows.map((r, i) => (
        <div key={r.company}>
          <div style={{ display: 'grid', gridTemplateColumns: cols.map((c) => c.width || '1fr').join(' '), gap: 14, padding: '8px 0', fontSize: 11.5, alignItems: 'center' }}>
            <div style={{ fontWeight: r.own ? 600 : 500, color: r.own ? DEEP_TEAL : INK_TEXT }}>{r.company}</div>
            <div style={{ color: r.theme ? INK_TEXT : MUTED, fontStyle: r.theme ? 'normal' : 'italic' }}>{r.theme || 'no capture yet'}</div>
            <div style={{ fontFamily: MONO, fontSize: 10, color: MUTED }}>{r.captured_at || '—'}</div>
          </div>
          {i < rows.length - 1 && <RowDivider />}
        </div>
      ))}
    </div>
  )
}

// ---------- Matrix 07 - footprint ----------

const FOOTPRINT_CHANNELS = ['search', 'meta_ads', 'ig_organic', 'tiktok', 'youtube', 'x', 'homepage']

function Footprint({ rows }) {
  const cols = [{ label: 'BRAND', width: '190px' }, ...FOOTPRINT_CHANNELS.map((id) => ({ label: CHANNEL_NAME[id].toUpperCase() }))]
  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ minWidth: 720 }}>
        <TableHead columns={cols} />
        {rows.map((r, i) => (
          <div key={r.company}>
            <div style={{ display: 'grid', gridTemplateColumns: cols.map((c) => c.width || '1fr').join(' '), gap: 14, padding: '8px 0', fontSize: 11.5, alignItems: 'center' }}>
              <div style={{ fontWeight: r.own ? 600 : 500, color: r.own ? DEEP_TEAL : INK_TEXT }}>{r.company}</div>
              {FOOTPRINT_CHANNELS.map((id) => {
                const has = r[id]
                const tracked = r.tracked[id] !== false
                return (
                  <div
                    key={id}
                    title={has ? 'Has content' : tracked ? 'No content in the tracker' : 'No handle recorded - not confirmed silence'}
                    style={{ fontFamily: MONO, fontWeight: 600, color: has ? GREEN : tracked ? SLATE_400 : MUTED, opacity: has ? 1 : 0.7 }}
                  >
                    {has ? '✓' : tracked ? '—' : '?'}
                  </div>
                )
              })}
            </div>
            {i < rows.length - 1 && <RowDivider />}
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------- Matrix 08 / 09 - simple horizontal bars ----------

function SimpleBar({ rows, valueKey, label, fmt, max }) {
  const usable = rows.filter((r) => r[valueKey] !== null && r[valueKey] !== undefined)
  const m = max || Math.max(...usable.map((r) => r[valueKey]), 1)
  return (
    <div>
      {usable.map((r) => (
        <div key={r.company} style={{ display: 'grid', gridTemplateColumns: '190px 1fr 80px', gap: 10, alignItems: 'center', padding: '4px 0' }}>
          <div style={{ fontSize: 11, fontWeight: r.own ? 600 : 500, color: r.own ? DEEP_TEAL : INK_TEXT, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {r.company}
          </div>
          <div style={{ height: 10, background: TRACK, borderRadius: 5, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${Math.max((r[valueKey] / m) * 100, 2)}%`, background: TEAL_700, borderRadius: 5 }} />
          </div>
          <div style={{ fontSize: 10.5, color: MUTED, fontFamily: MONO, textAlign: 'right' }}>{fmt ? fmt(r) : r[valueKey]} {label}</div>
        </div>
      ))}
    </div>
  )
}

// ---------- Matrix 10 - engagement by territory ----------

function EngagementTable({ engagement }) {
  const rows = ATTRIBUTE_ORDER
    .map((a) => ({ attribute: a, ...engagement[a] }))
    .filter((r) => r.n > 0)
    .sort((a, b) => b.mean - a.mean)
  const cols = [{ label: 'TERRITORY', width: '160px' }, { label: 'N', width: '70px' }, { label: 'MEDIAN', width: '90px' }, { label: 'MEAN', width: '90px' }]
  return (
    <div>
      <TableHead columns={cols} />
      {rows.map((r, i) => (
        <div key={r.attribute}>
          <div style={{ display: 'grid', gridTemplateColumns: cols.map((c) => c.width || '1fr').join(' '), gap: 14, padding: '7px 0', fontSize: 11.5, alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, color: INK_TEXT }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: ATTRIBUTE_COLORS[r.attribute], flex: 'none' }} />
              {ATTRIBUTE_SHORT[r.attribute]}
            </div>
            <div style={{ fontFamily: MONO, color: MUTED }}>{fmtNum(r.n)}</div>
            <div style={{ fontFamily: MONO }}>{fmtNum(r.median)}</div>
            <div style={{ fontFamily: MONO }}>{fmtNum(r.mean)}</div>
          </div>
          {i < rows.length - 1 && <RowDivider />}
        </div>
      ))}
    </div>
  )
}

// ---------- Evidence: verbatim quotes ----------

function Quote({ q }) {
  return (
    <div style={{ border: `1px solid ${SLATE_200}`, borderRadius: 10, padding: '13px 14px', background: '#FBFCFD' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 7, gap: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 700 }}>{q.company}</div>
        <div style={{ fontSize: 9.5, color: MUTED, fontFamily: MONO, flex: 'none' }}>{CHANNEL_NAME[q.channel_id]}</div>
      </div>
      <div style={{ fontSize: 13, lineHeight: 1.5, color: SLATE_600 }}>&ldquo;{q.text}&rdquo;</div>
      {q.attribute && (
        <div style={{ display: 'inline-block', marginTop: 9, fontSize: 9, fontWeight: 600, color: DEEP_TEAL, background: TEAL_WASH, borderRadius: 4, padding: '2px 7px' }}>
          {ATTRIBUTE_SHORT[q.attribute] || q.attribute}
        </div>
      )}
    </div>
  )
}

function QuoteGrid({ quotes }) {
  if (!quotes.length) return <div style={{ fontSize: 11, color: MUTED, fontStyle: 'italic' }}>No verbatim examples available for this set.</div>
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 12 }}>
      {quotes.map((q, i) => <Quote key={i} q={q} />)}
    </div>
  )
}

// ---------- Synthesis ----------

function Synthesis({ items }) {
  return (
    <div>
      {items.map((s, i) => (
        <div key={i} style={{ display: 'flex', gap: 12, padding: '10px 0', borderTop: i > 0 ? `1px solid ${SLATE_200}` : 'none' }}>
          <div style={{
            flex: 'none', fontSize: 9, fontWeight: 600, letterSpacing: '.07em', textTransform: 'uppercase',
            color: s.confidence === 'high' ? DEEP_TEAL : AMBER,
            background: s.confidence === 'high' ? TEAL_WASH : '#FEF6E7',
            borderRadius: 4, padding: '3px 7px', height: 'fit-content', marginTop: 2,
          }}>
            {s.confidence}
          </div>
          <div style={{ fontSize: 12.5, lineHeight: 1.5, color: INK_TEXT }}>{s.finding}</div>
        </div>
      ))}
    </div>
  )
}

// ---------- Top level ----------

export default function MessagingStudy({ onOpenBrand }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const load = () => {
    setError(null)
    api.messagingStudy().then(setData).catch((e) => setError(e.message))
  }
  useEffect(load, [])

  if (error) return (
    <div style={{ padding: '20px 0', color: MUTED }}>
      Couldn't load the messaging study ({error}).{' '}
      <span onClick={load} style={{ textDecoration: 'underline', cursor: 'pointer' }}>Try again</span>
    </div>
  )
  if (!data) return <PageSkeleton cards={2} gridItems={4} />

  return (
    <div>
      <div style={{ marginTop: 30, marginBottom: 4 }}>
        <div style={{ fontSize: 10, letterSpacing: '.16em', color: TEAL_700, fontWeight: 600, marginBottom: 7 }}>MESSAGING STUDY</div>
        <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: '-.02em' }}>What the auto service category is actually saying</h2>
        <p style={{ margin: '8px 0 0', fontSize: 13, color: SLATE_600, lineHeight: 1.5, maxWidth: 760 }}>
          Trailing {Math.round(data.window_days / 30)} months, computed live from the same tracker as the rest of this page.
          Every percentage is a real classified count, not a sample estimate.
        </p>
      </div>

      <SectionNumber num="M01" title="Territory by brand" />
      <Heatmap data={data} onOpenBrand={onOpenBrand} />

      <SectionNumber num="M02" title="The gap map" />
      <div style={cardStyle()}>
        <SubHead title="Portfolio vs. direct competitors, in percentage points" note="Right means the portfolio leans on a territory more than direct full-service competitors. Left means competitors own ground the portfolio has largely vacated." />
        <DivergingBars gap={data.gap} />
        <div style={{ marginTop: 20 }}>
          <SubHead title="Same territories, five benchmark segments" />
          <GapTable gap={data.gap} />
        </div>
      </div>

      <SectionNumber num="M03" title="Funnel posture" />
      <div style={cardStyle()}>
        <SubHead title="Portfolio + direct competitors, sorted by Do% descending" note="See is awareness, Think is consideration, Do is a direct call to act." />
        <FunnelPosture rows={data.funnel_posture} />
      </div>

      <SectionNumber num="M04" title="Channel x territory" />
      <div style={cardStyle()}>
        <SubHead title="Does the story change by channel?" note="Portfolio vs. best-in-class marketers, same territory mix, split by where it was said." />
        <ChannelTerritory rows={data.channel_territory} />
      </div>

      <SectionNumber num="M05" title="Content mix" />
      <div style={cardStyle()}>
        <SubHead title="Promotional vs. brand-building content" note="Same items, classified by what a post IS rather than what claim it's making." />
        <ContentMix rows={data.content_mix} />
      </div>

      <SectionNumber num="M06" title="Homepage leads" />
      <div style={cardStyle()}>
        <SubHead title="What every homepage led with, most recent capture" />
        <HomepageLeads rows={data.homepage_leads} />
      </div>

      <SectionNumber num="M07" title="Paid and organic footprint" />
      <div style={cardStyle()}>
        <SubHead title="Where each brand actually showed up" note="A '?' means no handle is recorded for that channel - absence isn't confirmed silence. A '—' means a handle is tracked but nothing was found." />
        <Footprint rows={data.footprint} />
      </div>

      <SectionNumber num="M08" title="Always-on vs. burst" />
      <div style={cardStyle()}>
        <SubHead title="Median days a paid-search creative has been running" note="High means evergreen creative left in market; low means frequent refresh." />
        <SimpleBar rows={data.ad_longevity} valueKey="median_days" label="days" fmt={(r) => `${r.median_days}d (n=${r.n})`} />
      </div>

      <SectionNumber num="M09" title="Creative variety" />
      <div style={cardStyle()}>
        <SubHead title="Distinct ad copy as a share of sampled paid social ads" note="High duplication means one creative running across many placements." />
        <SimpleBar rows={data.creative_variety} valueKey="distinct_pct" max={100} fmt={(r) => `${r.distinct_pct}% (n=${r.n})`} />
      </div>

      <SectionNumber num="M10" title="Engagement by territory" />
      <div style={cardStyle()}>
        <SubHead title="What organic audiences actually respond to" note="Median and mean engagement per organic post, pooled across every tracked brand. The gap between them is the signal: territories with high mean but similar median have real upside, not just consistent baseline response." />
        <EngagementTable engagement={data.engagement_by_territory} />
      </div>

      <SectionNumber num="EVIDENCE" title="The copy itself" />
      <div style={cardStyle()}>
        <SubHead title="Portfolio, paid social" />
        <QuoteGrid quotes={data.quotes_own} />
        <div style={{ marginTop: 22 }}>
          <SubHead title="Competitors, in territories the portfolio has vacated" />
          <QuoteGrid quotes={data.quotes_gap} />
        </div>
      </div>

      <SectionNumber num="SYNTHESIS" title="Where the gaps are" />
      <div style={cardStyle()}>
        <Synthesis items={data.synthesis} />
        <SoWhat>
          Scraped messaging shows what brands say, not what customers believe or what any of it earns. White space
          found this way is a hypothesis, not a proven opportunity.
        </SoWhat>
      </div>
    </div>
  )
}
