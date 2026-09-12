import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StageBar, MixCaption, ReadLine, TableHead, RowDivider } from '../components/Widgets'
import { fmtNum, verdict, dominantWord, mixLabel, MUTED, INK_TEXT, SLATE_600, SLATE_200, DEEP_TEAL, AMBER, INK, TEAL, TEAL_700 } from '../styles'

export default function Category({ meta, category, focusBrand, allCategories, onCategoryChange, onOpenBrand }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    api.category(category, focusBrand).then(setData)
  }, [category, focusBrand])

  return (
    <div>
      <ContextBar
        scopeLabel="SCOPE · ONE CATEGORY"
        note={`Category-level rollup. The brand in focus (${focusBrand}) sits in ${meta.brands.find((b) => b.name === focusBrand)?.category || ''} and is flagged below.`}
      />
      <SectionNumber num="04" title="Category Rollup" />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 18 }}>
        {allCategories.map((c) => {
          const active = c === category
          return (
            <button
              key={c}
              onClick={() => onCategoryChange(c)}
              style={{
                fontSize: 11.5, fontWeight: active ? 600 : 500, padding: '7px 13px', borderRadius: 20,
                background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
                border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
              }}
            >
              {c}
            </button>
          )
        })}
      </div>

      {!data ? <div style={{ padding: 40, color: MUTED }}>Loading…</div> : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1.7fr 1fr', gap: 14, marginBottom: 14 }}>
            <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '22px 24px' }}>
              <div style={{ fontSize: 10, letterSpacing: '.15em', color: TEAL_700, fontWeight: 600 }}>CATEGORY ROLLUP</div>
              <h1 style={{ margin: '8px 0 0', fontSize: 28, fontWeight: 600 }}>{category}</h1>
              <div style={{ fontSize: 12, color: MUTED, marginTop: 5 }}>{data.note} · {data.members.length} brands tracked</div>
              <div style={{ marginTop: 16 }}>
                <ReadLine text={categoryTakeaway(data)} />
              </div>
              <div style={{ display: 'flex', gap: 30, marginTop: 20, flexWrap: 'wrap' }}>
                <div style={{ width: 250 }}>
                  <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, marginBottom: 8 }}>CATEGORY AVERAGE MIX</div>
                  <StageBar mix={data.mix} height={13} radius={7} />
                  <MixCaption mix={data.mix} />
                </div>
                <div>
                  <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600 }}>CONSENSUS</div>
                  <div style={{ fontSize: 22, fontWeight: 600, marginTop: 4, color: DEEP_TEAL }}>{consensusLabel(data.spread)}</div>
                  <div style={{ fontSize: 10.5, color: MUTED, lineHeight: 1.4, maxWidth: 190 }}>
                    Widest gap between brands on any single stage is {Math.max(...data.spread)} points.
                  </div>
                </div>
              </div>
            </div>
            <div style={{ background: INK, color: '#FFFFFF', borderRadius: 12, padding: '20px 21px' }}>
              <div style={{ fontSize: 9.5, letterSpacing: '.13em', color: TEAL, fontWeight: 600, marginBottom: 12 }}>OUTLIERS IN THIS CATEGORY</div>
              {data.outliers.length ? data.outliers.map((o) => (
                <button
                  key={o.company}
                  onClick={() => onOpenBrand(o.company)}
                  style={{ display: 'block', width: '100%', textAlign: 'left', padding: '13px 0', borderTop: '1px solid #253039', background: 'none', border: 'none', borderTopStyle: 'solid', cursor: 'pointer', fontFamily: 'Poppins, sans-serif', color: '#FFFFFF' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{o.company}</div>
                    <div style={{ fontSize: 10, color: '#94A3B8', fontFamily: 'ui-monospace,Menlo,monospace' }}>{mixLabel(o.mix)}</div>
                  </div>
                  <div style={{ margin: '9px 0 7px' }}><StageBar mix={o.mix} height={8} radius={4} /></div>
                  <div style={{ fontSize: 10.5, color: '#C7CED9', lineHeight: 1.4 }}>
                    Runs {dominantWord(o.mix).toLowerCase()} against a category average of {mixLabel(data.mix)}.
                  </div>
                </button>
              )) : <div style={{ fontSize: 11, color: '#94A3B8', fontStyle: 'italic' }}>Not enough data yet to flag an outlier.</div>}
            </div>
          </div>

          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Brand by brand</div>
            <div style={{ fontSize: 11, color: MUTED, marginBottom: 16 }}>Small multiples, sorted by See-weight. Wide spread means the category has no shared playbook.</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 11 }}>
              {data.members.map((m) => {
                const flag = m.is_focus ? 'BRAND IN FOCUS' : m.is_outlier ? 'OUTLIER' : 'IN LINE'
                const flagColor = m.is_focus ? '#FFFFFF' : m.is_outlier ? AMBER : SLATE_600
                const flagBg = m.is_focus ? DEEP_TEAL : m.is_outlier ? '#FEF6E7' : '#F1F5F9'
                return (
                  <button
                    key={m.company}
                    onClick={() => onOpenBrand(m.company)}
                    style={{ textAlign: 'left', border: `1px solid ${SLATE_200}`, borderRadius: 10, padding: '13px 14px', cursor: 'pointer', background: '#FBFCFD', fontFamily: 'Poppins, sans-serif' }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.25, color: INK_TEXT }}>{m.company}</div>
                      <div style={{ flex: 'none', fontSize: 8.5, fontWeight: 600, letterSpacing: '.09em', padding: '2px 5px', borderRadius: 4, color: flagColor, background: flagBg }}>{flag}</div>
                    </div>
                    <div style={{ margin: '11px 0 7px' }}><StageBar mix={m.mix} height={9} radius={5} /></div>
                    <div style={{ fontSize: 10, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{mixLabel(m.mix)}</div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, paddingTop: 9, borderTop: '1px solid #F1F5F9', fontSize: 10, color: SLATE_600 }}>
                      <span>{fmtNum(m.monthly_output)}/mo</span><span>{m.active_channels}/7 channels</span>
                    </div>
                    <div style={{ fontSize: 10.5, color: INK_TEXT, marginTop: 8, lineHeight: 1.4 }}>{verdict(m.mix)}</div>
                  </button>
                )
              })}
            </div>
          </div>

          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px' }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Channel behaviour across the category</div>
            <div style={{ fontSize: 11, color: MUTED, marginBottom: 14 }}>Average scale of use and stage weighting per channel, with the messages that recur most.</div>
            <TableHead columns={[
              { label: 'CHANNEL', width: '1.1fr' }, { label: 'AVG. SCALE', width: '0.9fr' },
              { label: 'AVG. SEE/THINK/DO', width: '1.2fr' }, { label: 'RECURRING MESSAGES', width: '2.6fr' },
            ]} />
            {data.channel_rows.map((row, idx) => (
              <div key={row.channel.id}>
                <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr 1.2fr 2.6fr', gap: 14, padding: '13px 0', alignItems: 'start' }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{row.channel.name}</div>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>{row.avg_volume}</div>
                    <div style={{ fontSize: 9.5, color: MUTED }}>{row.channel.unit}</div>
                  </div>
                  <div>
                    <StageBar mix={row.mix} />
                    <MixCaption mix={row.mix} suffix="" />
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {row.messages.length ? row.messages.map((m, i) => (
                      <div key={i} style={{ fontSize: 10, padding: '4px 8px', borderRadius: 5, background: '#F8FAFC', border: `1px solid ${SLATE_200}`, borderLeft: `2px solid ${m.color}`, color: INK_TEXT }}>{m.text}</div>
                    )) : <span style={{ fontSize: 10, color: MUTED, fontStyle: 'italic' }}>no examples yet</span>}
                  </div>
                </div>
                {idx < data.channel_rows.length - 1 && <RowDivider />}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function consensusLabel(spread) {
  const max = Math.max(...spread)
  return max > 34 ? 'Fragmented' : max > 20 ? 'Loose' : 'Tight'
}

function categoryTakeaway(data) {
  const max = Math.max(...data.spread)
  let note
  if (max > 34) note = 'There is no shared playbook here: brands disagree sharply on where to spend attention.'
  else if (max > 20) note = 'Most brands cluster, but a few run a materially different plan.'
  else note = 'Brands here behave almost identically, so differentiation has to come from the message, not the mix.'
  return `The category averages ${mixLabel(data.mix)} across See, Think and Do — ${verdict(data.mix).toLowerCase()}. ${note}`
}
