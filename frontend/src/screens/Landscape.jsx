import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StageBar, MixCaption, Legend } from '../components/Widgets'
import { competesBadgeStyle, fmtNum, verdict, mixLabel, attributeRows, STAGES, MUTED, INK_TEXT, SLATE_200, DEEP_TEAL, TEAL, AMBER, TEAL_700, TRACK, INK } from '../styles'

export default function Landscape({ meta, onOpenBrand, onOpenCategory }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    api.landscape().then(setData)
  }, [])

  if (!data) return <div style={{ padding: 40, color: MUTED }}>Loading…</div>

  const totalBrands = meta.brands.length
  const ours = data.categories.find((c) => c.name === 'Our Brands')
  const { insights } = data

  const seeGap = insights.max_competitor_see_output_90d && insights.our_see_output_90d
    ? Math.round(insights.max_competitor_see_output_90d / Math.max(insights.our_see_output_90d, 1))
    : null

  return (
    <div>
      <ContextBar
        scopeLabel="SCOPE · ALL BRANDS"
        note="Every tracked brand and category. Click a brand to open its deep dive, or a category name for the rollup."
      />
      <SectionNumber num="01" title="The Landscape" />

      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 32, marginBottom: 22, flexWrap: 'wrap' }}>
        <div style={{ flex: '2 1 500px' }}>
          <div style={{ fontSize: 10, letterSpacing: '.16em', color: TEAL_700, fontWeight: 600, marginBottom: 7 }}>COMPETITIVE LANDSCAPE</div>
          <h1 style={{ margin: 0, fontSize: 30, fontWeight: 600, letterSpacing: '-.025em', lineHeight: 1.12, maxWidth: 760 }}>
            Who is buying attention, and who is buying intent
          </h1>
          <p style={{ margin: '8px 0 0', fontSize: 13, color: '#475569', lineHeight: 1.5, maxWidth: 760 }}>
            {totalBrands} brands across {data.categories.length} categories and 7 channels. The bar is the share of output
            aimed at See, Think and Do. Click any brand for its channel-by-channel evidence.
          </p>
        </div>
        <Legend />
      </div>

      {/* Key differences - up top, before any other detail */}
      {ours && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 14, marginBottom: 20 }}>
          <div style={{ background: INK, color: '#FFFFFF', borderRadius: 12, padding: '18px 20px' }}>
            <div style={{ fontSize: 9.5, letterSpacing: '.13em', color: TEAL, fontWeight: 600, marginBottom: 8 }}>OUR SEE CONTENT IS GETTING DROWNED OUT</div>
            <div style={{ fontSize: 13, lineHeight: 1.5, color: '#E2E8F0' }}>
              Our Brands posted <b style={{ color: '#FFFFFF' }}>{fmtNum(insights.our_see_output_90d)}</b> See-stage pieces in the
              last 90 days across the whole portfolio.{' '}
              {insights.max_competitor_see_category && (
                <>
                  <b style={{ color: '#FFFFFF' }}>{insights.max_competitor_see_category}</b> alone posted{' '}
                  <b style={{ color: '#FFFFFF' }}>{fmtNum(insights.max_competitor_see_output_90d)}</b>
                  {seeGap && seeGap > 1 ? <> — roughly <b style={{ color: TEAL }}>{seeGap}×</b> our volume.</> : '.'}
                </>
              )}{' '}
              The message quality isn't the gap — the frequency is.
            </div>
          </div>
          <div style={{ background: INK, color: '#FFFFFF', borderRadius: 12, padding: '18px 20px' }}>
            <div style={{ fontSize: 9.5, letterSpacing: '.13em', color: AMBER, fontWeight: 600, marginBottom: 8 }}>WE RUN DO-HEAVIER THAN THE MARKET</div>
            <div style={{ fontSize: 13, lineHeight: 1.5, color: '#E2E8F0' }}>
              Our Brands' output is <b style={{ color: '#FFFFFF' }}>{insights.our_do_pct}% Do</b>-stage, versus an average of{' '}
              <b style={{ color: '#FFFFFF' }}>{insights.other_categories_avg_do_pct}%</b> across every other tracked category.
              We're optimized to close, in a landscape that spends much more of its effort earning attention first.
            </div>
          </div>
        </div>
      )}

      {/* What the industry is actually saying */}
      <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>What the industry is actually saying, by stage</div>
        <div style={{ fontSize: 11, color: MUTED, marginBottom: 16 }}>
          Every real post/ad is classified into one message attribute (Safety, Trust, Price, etc). Each bar is the % of{' '}
          <b style={{ color: DEEP_TEAL }}>Our Brands'</b> vs. <b style={{ color: '#94A3B8' }}>the rest of the market's</b> classified
          output at this stage that touches that attribute - a real count, not a sample estimate.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 18 }}>
          {STAGES.map((s) => {
            const st = data.stage_themes?.[s.name]
            const rows = attributeRows(st?.our, st?.other)
            return (
              <div key={s.id}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                  <div style={{ width: 7, height: 7, borderRadius: 2, background: s.color, flex: 'none' }} />
                  <div style={{ fontSize: 11.5, fontWeight: 600 }}>{s.name}</div>
                  <div style={{ fontSize: 9, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>
                    ({st?.our?.total ?? 0} of ours, {st?.other?.total ?? 0} of theirs, classified)
                  </div>
                </div>
                {rows.length ? (
                  <div>
                    {rows.map((row, i) => (
                      <div key={row.attribute} style={{ padding: '7px 0', borderTop: i > 0 ? `1px solid ${SLATE_200}` : 'none' }}>
                        <div style={{ fontSize: 11, color: INK_TEXT, marginBottom: 5 }}>{row.attribute}</div>
                        <div title={`Our Brands: ${row.ourCount} of ${row.ourTotal} classified See-stage items (${row.ourPct}%)`} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                          <div style={{ flex: 1, height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${row.ourPct}%`, background: DEEP_TEAL, borderRadius: 3 }} />
                          </div>
                          <div style={{ width: 76, fontSize: 9, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{row.ourPct}% us</div>
                        </div>
                        <div title={`Rest of market: ${row.otherCount} of ${row.otherTotal} classified See-stage items (${row.otherPct}%)`} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ flex: 1, height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${row.otherPct}%`, background: '#CBD5E1', borderRadius: 3 }} />
                          </div>
                          <div style={{ width: 76, fontSize: 9, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{row.otherPct}% mkt</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>Not enough classified content yet.</div>}
              </div>
            )
          })}
        </div>
      </div>

      {/* Per-channel content comparison at the See stage */}
      <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>What we say vs. what the market says, by channel — See stage</div>
        <div style={{ fontSize: 11, color: MUTED, marginBottom: 16 }}>
          For each channel: themes both sides hit, themes only we hit, and themes only the rest of the market hits at the
          awareness (See) stage. This is where the content gap actually shows up, not just a volume number.
        </div>
        <ChannelContentComparison rows={data.channel_content} />
      </div>

      <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '4px 18px' }}>
        {data.categories.map((cat, idx) => (
          <div key={cat.name}>
            <div style={{ display: 'grid', gridTemplateColumns: '212px 198px 1fr', gap: 22, padding: '16px 0', alignItems: 'start' }}>
              <div>
                <button
                  onClick={() => onOpenCategory(cat.name)}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 14, fontWeight: 600, color: INK_TEXT, textAlign: 'left', fontFamily: 'Poppins, sans-serif' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = TEAL_700)}
                  onMouseLeave={(e) => (e.currentTarget.style.color = INK_TEXT)}
                >
                  {cat.name}
                </button>
                <div style={{ fontSize: 11, color: MUTED, margin: '4px 0 8px', lineHeight: 1.35 }}>{cat.note}</div>
                <div style={competesBadgeStyle(cat.competes, false)}>
                  {{ direct: 'DIRECT COMPETITOR', adjacent: 'ADJACENT INDUSTRY', 'read-across': 'READ-ACROSS', portfolio: 'OUR PORTFOLIO' }[cat.competes]}
                </div>
              </div>
              <div>
                <StageBar mix={cat.mix} />
                <MixCaption mix={cat.mix} />
                <div style={{ fontSize: 11.5, color: INK_TEXT, marginTop: 7, fontWeight: 500 }}>{verdict(cat.mix)}</div>
                <div style={{ fontSize: 10.5, color: MUTED, marginTop: 5 }}>See-share spread across brands: {cat.spread[0]}pts</div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 8 }}>
                {cat.profiles.map((p) => (
                  <button
                    key={p.company}
                    onClick={() => onOpenBrand(p.company)}
                    style={{
                      width: '100%', padding: '9px 11px 10px', border: `1px solid ${SLATE_200}`, borderRadius: 9,
                      cursor: 'pointer', background: '#FBFCFD', textAlign: 'left', fontFamily: 'Poppins, sans-serif',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#22B8C4'; e.currentTarget.style.background = '#FFFFFF' }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = SLATE_200; e.currentTarget.style.background = '#FBFCFD' }}
                  >
                    <div style={{ fontSize: 11.5, fontWeight: 500, lineHeight: 1.25, height: 29, overflow: 'hidden', color: INK_TEXT }}>{p.company}</div>
                    <StageBar mix={p.mix} height={6} radius={3} />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace', marginTop: 6 }}>
                      <span>{fmtNum(p.monthly_output)}/mo</span><span>{mixLabel(p.mix)}</span>
                    </div>
                  </button>
                ))}
              </div>
            </div>
            {idx < data.categories.length - 1 && <div style={{ height: 1, background: SLATE_200 }} />}
          </div>
        ))}
      </div>
    </div>
  )
}

// Per-channel: what content themes both sides hit, and where each side
// diverges - concrete "here's what's different", not an abstract percentage.
function ChannelContentComparison({ rows }) {
  if (!rows?.length) return <div style={{ fontSize: 11, color: MUTED, fontStyle: 'italic' }}>Not enough See-stage content captured yet.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {rows.map((r) => (
        <div key={r.channel.id} style={{ border: `1px solid ${SLATE_200}`, borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 9, flexWrap: 'wrap', gap: 6 }}>
            <div style={{ fontSize: 12.5, fontWeight: 600 }}>{r.channel.name}</div>
            <div style={{ fontSize: 9.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>
              {r.our_example_count} of ours vs {r.other_example_count} from the market, sampled
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
            <div>
              <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: DEEP_TEAL, fontWeight: 600, marginBottom: 6 }}>ONLY WE SAY</div>
              {r.our_only_themes?.length ? r.our_only_themes.map((t, i) => (
                <div key={i} style={{ fontSize: 10.5, color: INK_TEXT, padding: '3px 0' }}>{t}</div>
              )) : <div style={{ fontSize: 10, color: MUTED, fontStyle: 'italic' }}>—</div>}
            </div>
            <div>
              <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600, marginBottom: 6 }}>BOTH SIDES SAY</div>
              {r.shared_themes?.length ? r.shared_themes.map((t, i) => (
                <div key={i} style={{ fontSize: 10.5, color: INK_TEXT, padding: '3px 0' }}>{t}</div>
              )) : <div style={{ fontSize: 10, color: MUTED, fontStyle: 'italic' }}>—</div>}
            </div>
            <div>
              <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: AMBER, fontWeight: 600, marginBottom: 6 }}>ONLY THE MARKET SAYS</div>
              {r.other_only_themes?.length ? r.other_only_themes.map((t, i) => (
                <div key={i} style={{ fontSize: 10.5, color: INK_TEXT, padding: '3px 0' }}>{t}</div>
              )) : <div style={{ fontSize: 10, color: MUTED, fontStyle: 'italic' }}>—</div>}
            </div>
          </div>
          {r.note && <div style={{ fontSize: 10.5, color: MUTED, lineHeight: 1.4, marginTop: 10, paddingTop: 9, borderTop: `1px solid ${SLATE_200}`, fontStyle: 'italic' }}>{r.note}</div>}
        </div>
      ))}
    </div>
  )
}
