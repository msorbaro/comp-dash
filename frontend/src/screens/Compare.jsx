import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StageBar, MixCaption, TableHead, RowDivider } from '../components/Widgets'
import { fmtNum, verdict, MUTED, INK, SLATE_200, SLATE_600, SLATE_400, TEAL, TEAL_700, TRACK } from '../styles'

export default function Compare({ meta, brandA, brandB, onBrandAChange, onBrandBChange }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    setData(null)
    api.compare(brandA, brandB).then(setData)
  }, [brandA, brandB])

  return (
    <div>
      <ContextBar
        scopeLabel="SCOPE · TWO BRANDS"
        note="Side A is the brand in focus. Change either side to re-run the comparison."
      />
      <SectionNumber num="05" title="Head to Head" />

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 0.6fr 2fr', gap: 12, alignItems: 'end', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 10, letterSpacing: '.15em', color: TEAL_700, fontWeight: 600, marginBottom: 6 }}>SIDE A · BRAND IN FOCUS</div>
          <select value={brandA} onChange={(e) => onBrandAChange(e.target.value)} style={selectStyle}>
            {meta.brands.map((b) => <option key={b.name} value={b.name}>{b.name} — {b.category}</option>)}
          </select>
        </div>
        <div style={{ textAlign: 'center', fontSize: 10, letterSpacing: '.15em', color: MUTED, fontWeight: 600, paddingBottom: 10 }}>VS</div>
        <div>
          <div style={{ fontSize: 10, letterSpacing: '.15em', color: MUTED, fontWeight: 600, marginBottom: 6 }}>SIDE B</div>
          <select value={brandB} onChange={(e) => onBrandBChange(e.target.value)} style={selectStyle}>
            {meta.brands.filter((b) => b.name !== brandA).map((b) => <option key={b.name} value={b.name}>{b.name} — {b.category}</option>)}
          </select>
        </div>
      </div>

      {!data ? <div style={{ padding: 40, color: MUTED }}>Loading…</div> : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
            {[data.a, data.b].map((p, i) => {
              const dark = i === 0
              return (
                <div key={p.company} style={{
                  background: dark ? INK : '#FFFFFF', color: dark ? '#FFFFFF' : '#1A1F26',
                  border: dark ? 'none' : `1px solid ${SLATE_200}`, borderRadius: 12, padding: '22px 24px',
                }}>
                  <div style={{ fontSize: 9.5, letterSpacing: '.13em', fontWeight: 600, color: dark ? TEAL : TEAL_700 }}>{p.category.toUpperCase()}</div>
                  <h2 style={{ margin: '7px 0 0', fontSize: 23, fontWeight: 600 }}>{p.company}</h2>
                  <div style={{ margin: '16px 0 8px' }}>
                    <StageBar mix={p.mix} height={12} trackColor={dark ? 'rgba(255,255,255,.12)' : TRACK} />
                  </div>
                  <MixCaption mix={p.mix} color={dark ? SLATE_400 : MUTED} />
                  <div style={{ display: 'flex', gap: 24, marginTop: 16 }}>
                    {[
                      ['OUTPUT / MO', fmtNum(p.monthly_output)],
                      ['CHANNELS', `${p.active_channels}/7`],
                      ['CONSISTENCY', p.consistency != null ? String(p.consistency) : '—'],
                    ].map(([lbl, val]) => (
                      <div key={lbl}>
                        <div style={{ fontSize: 9, letterSpacing: '.12em', fontWeight: 600, color: dark ? SLATE_400 : MUTED }}>{lbl}</div>
                        <div style={{ fontSize: 18, fontWeight: 600, marginTop: 3 }}>{val}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ fontSize: 11.5, lineHeight: 1.45, marginTop: 15, color: dark ? '#C7CED9' : SLATE_600 }}>
                    {verdict(p.mix)}. Heaviest channel: {p.lead_channel_name}.
                  </div>
                </div>
              )
            })}
          </div>

          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px' }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Where they diverge</div>
            <div style={{ fontSize: 11, color: MUTED, marginBottom: 16 }}>Channel by channel: scale of use, stage weighting, and the gap worth acting on.</div>
            <TableHead columns={[
              { label: 'CHANNEL', width: '0.9fr' }, { label: brandA.toUpperCase(), width: '1.3fr' },
              { label: brandB.toUpperCase(), width: '1.3fr' }, { label: 'THE GAP', width: '1.7fr' },
            ]} />
            {data.rows.map((row, idx) => (
              <div key={row.channel.id}>
                <div style={{ display: 'grid', gridTemplateColumns: '0.9fr 1.3fr 1.3fr 1.7fr', gap: 16, padding: '14px 0', alignItems: 'center' }}>
                  <div style={{ fontSize: 12, fontWeight: 600 }}>{row.channel.name}</div>
                  {[row.a, row.b].map((side, i) => (
                    <div key={i}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, marginBottom: 6 }}>
                        <div style={{ fontSize: 15, fontWeight: 600 }}>{side.volume}</div>
                        <div style={{ fontSize: 9.5, color: MUTED }}>{row.channel.unit}</div>
                      </div>
                      <StageBar mix={side.split} height={9} radius={5} />
                      <MixCaption mix={side.split} suffix="" />
                    </div>
                  ))}
                  <div style={{ fontSize: 11, lineHeight: 1.4, color: '#1A1F26' }}>{gapText(brandA, row)}</div>
                </div>
                {idx < data.rows.length - 1 && <RowDivider />}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const selectStyle = {
  width: '100%', background: '#FFFFFF', border: '1px solid #CBD5E1', borderRadius: 7,
  padding: '7px 10px', fontFamily: 'Poppins, sans-serif', fontSize: 12, boxSizing: 'border-box',
}

function gapText(brandAName, row) {
  const dVol = row.a.volume - row.b.volume
  const dSee = row.a.split[0] - row.b.split[0]
  const dDo = row.a.split[2] - row.b.split[2]
  const big = Math.abs(dSee) >= Math.abs(dDo)
  if (Math.abs(dVol) < 3 && Math.abs(dSee) < 6 && Math.abs(dDo) < 6) {
    return 'Effectively the same play — no advantage either way.'
  }
  const diff = big ? dSee : dDo
  return `${brandAName} runs ${Math.abs(dVol)} ${dVol >= 0 ? 'more' : 'fewer'} ${row.channel.unit} and is ` +
    `${Math.abs(diff)}pts ${diff >= 0 ? 'heavier' : 'lighter'} on ${big ? 'See' : 'Do'}.`
}
