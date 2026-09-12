import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StatCard, StageBar, MixCaption, Legend } from '../components/Widgets'
import { competesBadgeStyle, fmtNum, verdict, mixLabel, MUTED, INK_TEXT, SLATE_200, TEAL_700 } from '../styles'

export default function Landscape({ meta, onOpenBrand, onOpenCategory }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    api.landscape().then(setData)
  }, [])

  if (!data) return <div style={{ padding: 40, color: MUTED }}>Loading…</div>

  const totalBrands = meta.brands.length
  const ours = data.categories.find((c) => c.name === 'Our Brands')
  const seeSorted = [...data.categories].sort((a, b) => b.mix[0] - a.mix[0])
  const doSorted = [...data.categories].sort((a, b) => b.mix[2] - a.mix[2])

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
            Every tracked brand scored across seven channels. The bar is the share of that brand's output aimed at
            See, Think and Do. Click any brand for its channel-by-channel evidence.
          </p>
        </div>
        <Legend />
      </div>

      {ours && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
          <StatCard label="BRANDS TRACKED" value={String(totalBrands)} note={`${data.categories.length} categories, 7 channels each`} />
          <StatCard label="OUR PORTFOLIO MIX" value={mixLabel(ours.mix)} note={verdict(ours.mix).toLowerCase()} />
          <StatCard label="MOST SEE-WEIGHTED" value={`${seeSorted[0].mix[0]}%`} note={`${seeSorted[0].name} buys the most attention`} />
          <StatCard label="MOST DO-WEIGHTED" value={`${doSorted[0].mix[2]}%`} note={`${doSorted[0].name} runs hardest at intent`} />
        </div>
      )}

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
