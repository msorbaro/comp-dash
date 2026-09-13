import { useEffect, useState } from 'react'
import { api } from '../api'
import ContextBar from '../components/ContextBar'
import { SectionNumber, StageBar, MixCaption, ReadLine, TableHead, RowDivider } from '../components/Widgets'
import { fmtNum, verdict, mixLabel, attributeRows, STAGES, MUTED, INK_TEXT, SLATE_600, SLATE_200, DEEP_TEAL, AMBER, TEAL_700, TRACK } from '../styles'

export default function Category({ meta, category, focusBrand, allCategories, onCategoryChange, onOpenBrand }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const load = () => {
    setData(null)
    setError(null)
    api.category(category, focusBrand).then(setData).catch((e) => setError(e.message))
  }
  useEffect(load, [category, focusBrand])

  return (
    <div>
      <ContextBar
        scopeLabel="SCOPE · ONE CATEGORY"
        note={`Category-level rollup. The brand in focus (${focusBrand}) sits in ${meta.brands.find((b) => b.name === focusBrand)?.category || ''} and is flagged below.`}
      />
      <SectionNumber num="04" title="Category Rollup" />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 18 }}>
        {[...allCategories].sort((a, b) => (a === 'Our Brands' ? -1 : b === 'Our Brands' ? 1 : 0)).map((c) => {
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

      {error ? (
        <div style={{ padding: 40, color: MUTED }}>
          Couldn't load this category ({error}).{' '}
          <span onClick={load} style={{ textDecoration: 'underline', cursor: 'pointer' }}>Try again</span>
        </div>
      ) : !data ? <div style={{ padding: 40, color: MUTED }}>Loading…</div> : (
        <>
          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '22px 24px', marginBottom: 14 }}>
            <div style={{ fontSize: 10, letterSpacing: '.15em', color: TEAL_700, fontWeight: 600 }}>CATEGORY ROLLUP</div>
            <h1 style={{ margin: '8px 0 0', fontSize: 28, fontWeight: 600 }}>{category}</h1>
            <div style={{ fontSize: 12, color: MUTED, marginTop: 5 }}>{data.note} · {data.members.length} brands tracked</div>
            <div style={{ marginTop: 16 }}>
              <ReadLine text={categoryTakeaway(data)} />
            </div>
            <div style={{ display: 'flex', gap: 40, marginTop: 20, flexWrap: 'wrap' }}>
              <div style={{ maxWidth: 420, flex: '1 1 360px' }}>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, marginBottom: 8 }}>
                  CATEGORY SEE / THINK / DO MIX — averaged across all {data.members.length} brands
                </div>
                <StageBar mix={data.mix} height={13} radius={7} />
                <MixCaption mix={data.mix} />
              </div>
              <div style={{ flex: '1 1 360px', minWidth: 300 }}>
                <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, marginBottom: 8 }}>
                  CHANNEL VOLUME — total output across all brands, last 90 days
                </div>
                <ChannelVolumeChart rows={data.channel_rows} />
              </div>
            </div>
            <div style={{ marginTop: 22, paddingTop: 18, borderTop: `1px solid ${SLATE_200}` }}>
              <div style={{ fontSize: 9.5, letterSpacing: '.12em', color: MUTED, fontWeight: 600, marginBottom: 3 }}>
                WHAT BRANDS ARE ACTUALLY SAYING, BY STAGE
              </div>
              <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 14 }}>
                Every real post/ad from the category's {data.members.length} brands is classified into one message attribute
                (Safety, Trust, Price, etc). Bars are the real % of classified output at each stage that touches each attribute.
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 18 }}>
                {STAGES.map((s) => {
                  const st = data.stage_themes?.[s.name]
                  const rows = attributeRows(st)
                  return (
                    <div key={s.id}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
                        <div style={{ width: 7, height: 7, borderRadius: 2, background: s.color, flex: 'none' }} />
                        <div style={{ fontSize: 11.5, fontWeight: 600 }}>{s.name}</div>
                        <div style={{ fontSize: 9, color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>({st?.total ?? 0} classified)</div>
                      </div>
                      {rows.length ? (
                        <div>
                          {rows.map((row, i) => (
                            <div key={row.attribute} style={{ padding: '6px 0', borderTop: i > 0 ? `1px solid ${SLATE_200}` : 'none' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: INK_TEXT, marginBottom: 4 }}>
                                <span>{row.attribute}</span>
                                <span style={{ color: MUTED, fontFamily: 'ui-monospace,Menlo,monospace' }}>{row.ourPct}%</span>
                              </div>
                              <div style={{ height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden' }}>
                                <div style={{ height: '100%', width: `${row.ourPct}%`, background: DEEP_TEAL, borderRadius: 3 }} />
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>Not enough classified content yet.</div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          <div style={{ background: '#FFFFFF', border: `1px solid ${SLATE_200}`, borderRadius: 12, padding: '20px 22px', marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Brand by brand</div>
            <div style={{ fontSize: 11, color: MUTED, marginBottom: 16 }}>Our brands first, then the rest sorted by See-weight. Wide spread means the category has no shared playbook.</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 11 }}>
              {[...data.members].sort((a, b) => {
                const aOwn = meta.brands.find((b2) => b2.name === a.company)?.is_own_brand ? 1 : 0
                const bOwn = meta.brands.find((b2) => b2.name === b.company)?.is_own_brand ? 1 : 0
                return bOwn - aOwn
              }).map((m) => {
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
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 3 }}>Channel adoption &amp; use across the category</div>
            <div style={{ fontSize: 11, color: MUTED, marginBottom: 14 }}>
              Which channels this category actually runs, how much they post there, the See/Think/Do split when they do, and the recurring cross-brand themes on each. Sorted by adoption.
            </div>
            <TableHead columns={[
              { label: 'CHANNEL', width: '1.2fr' }, { label: 'ADOPTION', width: '1.3fr' },
              { label: '90-DAY VOLUME', width: '1fr' }, { label: 'SEE/THINK/DO (WHEN USED)', width: '1.3fr' },
              { label: 'RECURRING THEMES', width: '2.6fr' },
            ]} />
            {data.channel_rows.map((row, idx) => {
              const pct = Math.round((row.brands_using / row.brands_total) * 100)
              return (
              <div key={row.channel.id}>
                <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.3fr 1fr 1.3fr 2.6fr', gap: 14, padding: '13px 0', alignItems: 'start' }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{row.channel.name}</div>
                    <div style={{ fontSize: 9.5, color: MUTED, marginTop: 2 }}>{row.channel.paid ? 'Paid' : 'Owned / organic'}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{row.brands_using} of {row.brands_total} brands</div>
                    <div style={{ height: 5, background: TRACK, borderRadius: 3, overflow: 'hidden', marginTop: 5, maxWidth: 130 }}>
                      <div style={{ height: '100%', width: `${pct}%`, background: pct >= 50 ? DEEP_TEAL : AMBER, borderRadius: 3 }} />
                    </div>
                    <div style={{ fontSize: 9.5, color: MUTED, marginTop: 3 }}>{pct}% actively use this</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 16, fontWeight: 600 }}>{fmtNum(row.total_volume_90)}</div>
                    <div style={{ fontSize: 9.5, color: MUTED }}>{row.channel.unit}, last 90 days, category-wide</div>
                  </div>
                  <div>
                    <StageBar mix={row.mix} />
                    <MixCaption mix={row.mix} suffix="" />
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {row.themes.length ? row.themes.map((t, i) => (
                      <div key={i} style={{ fontSize: 10, padding: '4px 8px', borderRadius: 5, background: '#F8FAFC', border: `1px solid ${SLATE_200}`, color: INK_TEXT }}>{t}</div>
                    )) : <span style={{ fontSize: 10, color: MUTED, fontStyle: 'italic' }}>no clear cross-brand pattern yet</span>}
                  </div>
                </div>
                {idx < data.channel_rows.length - 1 && <RowDivider />}
              </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

// Horizontal bar chart: one series (90-day volume), color splits on paid vs
// owned/organic since that distinction already reads consistently everywhere
// else in this app (see paidChipStyle) - reusing it here instead of a new
// categorical ramp. Direct-labeled (channel name + value) since there are
// only 7 bars; a hover title gives the full sentence for anyone who wants it.
function ChannelVolumeChart({ rows }) {
  const sorted = [...rows].sort((a, b) => b.total_volume_90 - a.total_volume_90)
  const max = Math.max(...sorted.map((r) => r.total_volume_90), 1)
  return (
    <div>
      <div style={{ display: 'flex', gap: 14, marginBottom: 9, fontSize: 10, color: MUTED }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: AMBER, display: 'inline-block' }} /> Paid
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
          <span style={{ width: 8, height: 8, borderRadius: 2, background: TEAL_700, display: 'inline-block' }} /> Owned / organic
        </span>
      </div>
      {sorted.map((r) => (
        <div
          key={r.channel.id}
          title={`${r.channel.name}: ${r.total_volume_90} ${r.channel.unit} in the last 90 days across the category`}
          style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 7 }}
        >
          <div style={{ width: 108, fontSize: 10.5, color: INK_TEXT, flex: 'none', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {r.channel.name}
          </div>
          <div style={{ flex: 1, height: 12, background: TRACK, borderRadius: 6, overflow: 'hidden' }}>
            <div style={{
              height: '100%', borderRadius: 6, background: r.channel.paid ? AMBER : TEAL_700,
              width: `${r.total_volume_90 > 0 ? Math.max((r.total_volume_90 / max) * 100, 3) : 0}%`,
            }} />
          </div>
          <div style={{ width: 34, fontSize: 10.5, color: MUTED, flex: 'none', fontFamily: 'ui-monospace,Menlo,monospace' }}>
            {fmtNum(r.total_volume_90)}
          </div>
        </div>
      ))}
    </div>
  )
}

function categoryTakeaway(data) {
  const max = Math.max(...data.spread)
  let note
  if (max > 34) note = 'There is no shared playbook here: brands disagree sharply on where to spend attention.'
  else if (max > 20) note = 'Most brands cluster, but a few run a materially different plan.'
  else note = 'Brands here behave almost identically, so differentiation has to come from the message, not the mix.'
  return `The category averages ${mixLabel(data.mix)} across See, Think and Do — ${verdict(data.mix).toLowerCase()}. ${note}`
}
