import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StageBar, MixCaption, ChannelBar, topChannelsLabel, Legend, PageSkeleton } from '../components/Widgets'
import PostingCadence from '../components/PostingCadence'
import BrandMatrix from '../components/BrandMatrix'
import ValueMap from '../components/ValueMap'
import { competesBadgeStyle, fmtNum, verdict, mixLabel, attributeRows, STAGES, MUTED, INK_TEXT, SLATE_200, SLATE_600, DEEP_TEAL, TEAL, AMBER, TEAL_700, TRACK, INK } from '../styles'

export default function Landscape({ meta, onOpenBrand, onOpenCategory }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [gridMode, setGridMode] = useState('stage')

  const load = () => {
    setError(null)
    api.landscape().then(setData).catch((e) => setError(e.message))
  }
  useEffect(load, [])

  if (error) return (
    <div style={{ padding: 40, color: MUTED }}>
      Couldn't load this page ({error}).{' '}
      <span onClick={load} style={{ textDecoration: 'underline', cursor: 'pointer' }}>Try again</span>
    </div>
  )
  if (!data) return <PageSkeleton cards={2} gridItems={8} />

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

      <PostingCadence categories={data.categories.map((c) => c.name)} />

      <BrandMatrix categories={data.categories.map((c) => c.name)} />

      <ValueMap categories={data.categories.map((c) => c.name)} />

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

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontSize: 11, color: MUTED }}>Every category and the brands in it - by stage mix or by which channels they actually run.</div>
        <div style={{ display: 'flex', gap: 5 }}>
          <button
            onClick={() => setGridMode('stage')}
            style={pillStyle(gridMode === 'stage')}
          >
            Stage mix
          </button>
          <button
            onClick={() => setGridMode('channel')}
            style={pillStyle(gridMode === 'channel')}
          >
            Channel mix
          </button>
        </div>
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
                {gridMode === 'stage' ? (
                  <>
                    <StageBar mix={cat.mix} />
                    <MixCaption mix={cat.mix} />
                    <div style={{ fontSize: 11.5, color: INK_TEXT, marginTop: 7, fontWeight: 500 }}>{verdict(cat.mix)}</div>
                    <div style={{ fontSize: 10.5, color: MUTED, marginTop: 5 }}>See-share spread across brands: {cat.spread[0]}pts</div>
                  </>
                ) : (
                  <>
                    <ChannelBar totals={cat.channel_totals} />
                    <div style={{ fontSize: 10.5, color: MUTED, marginTop: 7, fontFamily: 'ui-monospace,Menlo,monospace' }}>{topChannelsLabel(cat.channel_totals, 3)}</div>
                  </>
                )}
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
                    {gridMode === 'stage' ? (
                      <>
                        <StageBar mix={p.mix} height={6} radius={3} />
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace', marginTop: 6 }}>
                          <span>{fmtNum(p.monthly_output)}/mo</span><span>{mixLabel(p.mix)}</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <ChannelBar totals={p.channel_mix} height={6} radius={3} />
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9.5, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace', marginTop: 6 }}>
                          <span>{fmtNum(p.monthly_output)}/mo</span><span>{topChannelsLabel(p.channel_mix, 1)}</span>
                        </div>
                      </>
                    )}
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

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}
