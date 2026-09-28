import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api'
import { RowDivider } from './Widgets'
import {
  MUTED, INK_TEXT, SLATE_600, SLATE_400, SLATE_200, DEEP_TEAL, TEAL_700, TEAL_WASH, CANVAS,
  MONO, GREEN, ROSE, fmtNum,
} from '../styles'

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

function selectStyle() {
  return { fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }
}

// Same full-bleed section-band treatment as the Reviews page's Section
// component (see VoiceReviewTrend.jsx) - -22px matches Voice.jsx's cardBase
// 22px horizontal padding.
function Section({ title, scope, children }) {
  return (
    <div style={{ marginTop: 44 }}>
      <div style={{ background: CANVAS, margin: '0 -22px', padding: '18px 22px 16px', borderTop: `1px solid ${SLATE_200}`, borderBottom: `1px solid ${SLATE_200}` }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: INK_TEXT, marginBottom: scope ? 6 : 0 }}>{title}</div>
        {scope && (
          <div style={{ fontSize: 10.5, color: TEAL_700, fontWeight: 600, background: TEAL_WASH, display: 'inline-block', padding: '3px 9px', borderRadius: 12 }}>
            {scope}
          </div>
        )}
      </div>
      <div style={{ paddingTop: 18 }}>{children}</div>
    </div>
  )
}

// A comment's permalink comes back from the scraper as whatever Reddit's own
// API gave it - a post's is already a full URL, but a comment's is often
// just the site-relative path (see voice/reddit_mentions.py's `_write_items`,
// which stores each type's field as-is rather than normalizing it).
function redditUrl(permalink) {
  if (!permalink) return null
  return permalink.startsWith('http') ? permalink : `https://www.reddit.com${permalink}`
}

const THEME_LABELS = {
  complaint: 'complaint', question: 'question', recommendation: 'recommendation',
  price_or_deal: 'price/deal', comparison: 'comparison', employment: 'employment', news: 'news', other: 'other',
}

// The aspect-theme taxonomy (categorize/reddit_mention_themes.py, same set
// as categorize/review_themes.py) - distinct from THEME_LABELS above, which
// is the post-purpose classification (complaint/question/etc).
const ASPECT_LABELS = {
  price_value: 'Price / value', speed_wait_time: 'Speed / wait time', customer_service: 'Customer service',
  technical_quality: 'Technical quality', honesty_trust: 'Honesty / trust', upselling_pressure: 'Upselling / pressure',
  convenience_location: 'Convenience / location', scheduling_ease: 'Scheduling ease', communication: 'Communication',
  cleanliness_facility: 'Cleanliness / facility', warranty_followup: 'Warranty / follow-up',
  product_selection: 'Product selection', other: 'Other',
}

const ASPECT_ORDER = Object.keys(ASPECT_LABELS)

// Same design as the Reviews page's NegativeAttributeChart - one compact
// multi-attribute bar block per brand, all shown at once (no brand
// selector) so brands are directly comparable. Reddit has no star rating,
// so the "negative" population here is overall mention sentiment instead
// (see reddit_negative_theme_mix's own docstring for that reasoning).
function NegativeAttributeChart({ data }) {
  if (data === null) return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>Loading…</div>
  const withData = data.filter((b) => b.n_negative > 0)
  if (withData.length === 0) return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No matching mentions.</div>
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {withData.map((b) => {
        const byTheme = Object.fromEntries(b.themes.map((t) => [t.theme, t]))
        return (
          <div key={b.brand_id} style={{ background: b.mavis ? TEAL_WASH : 'transparent', borderRadius: 8, padding: b.mavis ? '10px 12px' : '0 0 4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, justifyContent: 'space-between', marginBottom: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: b.mavis ? 600 : 500 }}>
                {b.logo && <img src={b.logo} alt="" width={14} height={14} style={{ borderRadius: 3, flex: 'none' }} onError={(e) => { e.currentTarget.style.display = 'none' }} />}
                {b.name}
                {b.mavis && <span style={{ color: TEAL_700, fontSize: 9, fontFamily: MONO, fontWeight: 600 }}>MAVIS</span>}
              </div>
              <div style={{ fontSize: 10.5, color: MUTED, fontFamily: MONO, flex: 'none' }}>{fmtNum(b.n_negative)} mentions</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 20px' }}>
              {ASPECT_ORDER.map((theme) => {
                const pct = byTheme[theme]?.pct || 0
                return (
                  <div key={theme} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 112, flex: 'none', fontSize: 10, color: SLATE_600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {ASPECT_LABELS[theme]}
                    </div>
                    <div style={{ flex: 1, background: SLATE_200, height: 7, borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ width: `${pct * 100}%`, height: '100%', background: ROSE }} />
                    </div>
                    <div style={{ width: 32, flex: 'none', fontSize: 9.5, fontFamily: MONO, color: MUTED, textAlign: 'right' }}>{Math.round(pct * 100)}%</div>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function MixBar({ n_positive, n_neutral, n_negative }) {
  const total = n_positive + n_neutral + n_negative
  if (total === 0) return <span style={{ fontSize: 11, color: MUTED }}>—</span>
  const title = `${n_positive} positive · ${n_neutral} neutral · ${n_negative} negative`
  return (
    <div style={{ display: 'flex', height: 10, borderRadius: 1, overflow: 'hidden', minWidth: 80 }} title={title}>
      {n_positive > 0 && <div style={{ width: `${(n_positive / total) * 100}%`, background: GREEN }} />}
      {n_neutral > 0 && <div style={{ width: `${(n_neutral / total) * 100}%`, background: SLATE_400 }} />}
      {n_negative > 0 && <div style={{ width: `${(n_negative / total) * 100}%`, background: ROSE }} />}
    </div>
  )
}

// The same per-aspect breakdown + "why negative -> summary -> see all
// mentions" interaction as the Reviews page's ThemeMixChart, just reading
// { theme, positive, neutral, negative, total } rows shaped identically to
// review_theme_mix's output.

// One polarity's expand-to-summary control (negative = complaints, positive
// = praise) - identical interaction, just mirrored colors/copy, so both
// directions of "what are people actually saying" are equally reachable
// (per the user's own framing: not just complaints, also who's posting
// positively and about what).
function ThemeSentimentLink({ theme, sentiment, count, complaint, isOpen, onToggle, onSeeMentions }) {
  const color = sentiment === 'negative' ? ROSE : GREEN
  const bg = sentiment === 'negative' ? '#FDF2F4' : '#F0FAF3'
  const verb = sentiment === 'negative' ? "What's the complaint?" : "What's the praise?"
  const emptyMsg = sentiment === 'negative' ? 'Not enough negative mentions to summarize.' : 'Not enough positive mentions to summarize.'
  return (
    <div style={{ marginTop: 5 }}>
      <span onClick={() => onToggle(theme, sentiment)} style={{ fontSize: 10, color, cursor: 'pointer', fontWeight: 600 }}>
        {isOpen ? 'Hide summary ▲' : `${verb} (${count} ${sentiment}) →`}
      </span>
      {isOpen && (
        <div style={{ marginTop: 6, background: bg, borderLeft: `3px solid ${color}`, borderRadius: 4, padding: '9px 11px', fontSize: 11.5, lineHeight: 1.55, color: INK_TEXT, maxWidth: '70ch' }}>
          {!complaint || complaint.loading ? 'Summarizing…' : complaint.summary || emptyMsg}
          {complaint && !complaint.loading && (
            <div style={{ marginTop: 8 }}>
              <span onClick={() => onSeeMentions(theme, sentiment)} style={{ fontSize: 10.5, color: DEEP_TEAL, cursor: 'pointer', fontWeight: 600, textDecoration: 'underline' }}>
                See all these mentions ↓
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function AspectMixChart({ themes, complaintsByTheme, openTheme, onToggle, onSeeMentions }) {
  if (themes === null) return <div style={{ padding: 16, color: MUTED, fontSize: 12 }}>Loading…</div>
  if (themes.length === 0) return <div style={{ padding: 16, color: MUTED, fontSize: 12 }}>No themed mentions for this brand yet.</div>
  const maxTotal = Math.max(...themes.map((t) => t.total))
  return (
    <div>
      {themes.map((t) => (
        <div key={t.theme} style={{ padding: '6px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 3 }}>
            <span style={{ fontWeight: 600 }}>{ASPECT_LABELS[t.theme] || t.theme}</span>
            <span style={{ color: MUTED, fontFamily: MONO }}>{t.total} mention{t.total === 1 ? '' : 's'}</span>
          </div>
          <div style={{ display: 'flex', height: 10, borderRadius: 1, overflow: 'hidden', width: `${Math.max(8, (t.total / maxTotal) * 100)}%`, minWidth: 60 }}>
            {t.positive > 0 && <div style={{ width: `${(t.positive / t.total) * 100}%`, background: GREEN }} title={`${t.positive} positive`} />}
            {t.neutral > 0 && <div style={{ width: `${(t.neutral / t.total) * 100}%`, background: SLATE_400 }} title={`${t.neutral} neutral`} />}
            {t.negative > 0 && <div style={{ width: `${(t.negative / t.total) * 100}%`, background: ROSE }} title={`${t.negative} negative`} />}
          </div>
          {t.positive > 0 && (
            <ThemeSentimentLink
              theme={t.theme} sentiment="positive" count={t.positive}
              complaint={complaintsByTheme[`${t.theme}|positive`]}
              isOpen={openTheme?.theme === t.theme && openTheme?.sentiment === 'positive'}
              onToggle={onToggle} onSeeMentions={onSeeMentions}
            />
          )}
          {t.negative > 0 && (
            <ThemeSentimentLink
              theme={t.theme} sentiment="negative" count={t.negative}
              complaint={complaintsByTheme[`${t.theme}|negative`]}
              isOpen={openTheme?.theme === t.theme && openTheme?.sentiment === 'negative'}
              onToggle={onToggle} onSeeMentions={onSeeMentions}
            />
          )}
        </div>
      ))}
    </div>
  )
}

const BRAND_COLUMN_WIDTHS = ['24px', '2.4fr', '90px', '90px', '1.4fr']

function BrandTable({ rows, expandedBrand, onToggleExpand, brandThemeMix, complaintsByTheme, openComplaint, onToggleComplaint, onSeeMentions }) {
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: BRAND_COLUMN_WIDTHS.join(' '), gap: 12 }}>
        <div />
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600 }}>BRAND</div>
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600, textAlign: 'right' }}>SCRAPED</div>
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600, textAlign: 'right' }}>RELEVANT</div>
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600 }}>SENTIMENT MIX</div>
      </div>
      <hr style={{ margin: '6px 0 4px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
      {rows.map((r) => {
        const isOpen = expandedBrand === r.name
        const canExpand = r.n_relevant > 0
        return (
          <div key={r.brand_id}>
            <div
              onClick={() => canExpand && onToggleExpand(r.name)}
              style={{ display: 'grid', gridTemplateColumns: BRAND_COLUMN_WIDTHS.join(' '), gap: 12, padding: '8px 0', fontSize: 12, background: r.mavis ? TEAL_WASH : 'transparent', cursor: canExpand ? 'pointer' : 'default' }}
            >
              <div style={{ color: DEEP_TEAL, fontSize: 10 }}>{canExpand ? (isOpen ? '▼' : '▶') : ''}</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: r.mavis ? 600 : 400 }}>
                {r.logo && <img src={r.logo} alt="" width={14} height={14} style={{ borderRadius: 3, flex: 'none' }} onError={(e) => { e.currentTarget.style.display = 'none' }} />}
                {r.name}
                {r.mavis && <span style={{ color: TEAL_700, fontSize: 9.5, fontFamily: MONO, fontWeight: 600, paddingLeft: 6, letterSpacing: '.05em' }}>MAVIS</span>}
              </div>
              <div style={{ textAlign: 'right', fontFamily: MONO, color: MUTED }}>{fmtNum(r.n_scraped)}</div>
              <div style={{ textAlign: 'right', fontFamily: MONO, fontWeight: 600 }}>{fmtNum(r.n_relevant)}</div>
              <div><MixBar {...r} /></div>
            </div>
            {isOpen && (
              <div style={{ padding: '10px 10px 14px 34px', background: '#FAFBFB', borderRadius: 6, marginBottom: 4 }}>
                <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 8 }}>
                  What Reddit discussions about <strong style={{ color: INK_TEXT }}>{r.name}</strong> are actually about - extracted from post/comment text.
                </div>
                <AspectMixChart
                  themes={brandThemeMix[r.name] ?? null}
                  complaintsByTheme={complaintsByTheme[r.name] || {}}
                  openTheme={openComplaint?.brand === r.name ? { theme: openComplaint.theme, sentiment: openComplaint.sentiment } : null}
                  onToggle={(theme, sentiment) => onToggleComplaint(r.name, theme, sentiment)}
                  onSeeMentions={(theme, sentiment) => onSeeMentions(r.name, theme, sentiment)}
                />
              </div>
            )}
            <RowDivider />
          </div>
        )
      })}
    </div>
  )
}

function MentionCard({ m }) {
  const sentColor = m.sentiment === 'positive' ? GREEN : m.sentiment === 'negative' ? ROSE : SLATE_400
  const url = redditUrl(m.permalink)
  return (
    <div style={{ padding: '10px 0' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 4, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 12 }}>
          <span style={{ fontWeight: 600 }}>{m.brand}</span>
          {m.mavis && <span style={{ color: TEAL_700, fontSize: 9.5, fontFamily: MONO, fontWeight: 600, paddingLeft: 6 }}>MAVIS</span>}
          <span style={{ color: MUTED }}> · r/{m.subreddit || '?'} · {m.type} · {m.date || 'undated'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flex: 'none' }}>
          {m.score !== null && m.score !== undefined && <span style={{ fontFamily: MONO, fontSize: 11, color: MUTED }}>▲{fmtNum(m.score)}</span>}
          {m.theme && (
            <span style={{ fontSize: 9.5, fontWeight: 600, color: SLATE_600, background: '#EEF2F3', borderRadius: 4, padding: '2px 6px', textTransform: 'uppercase', letterSpacing: '.03em' }}>
              {THEME_LABELS[m.theme] || m.theme}
            </span>
          )}
          <span style={{ fontSize: 9.5, fontWeight: 600, color: '#FFFFFF', background: sentColor, borderRadius: 4, padding: '2px 6px', textTransform: 'uppercase', letterSpacing: '.04em' }}>
            {m.sentiment || 'pending'}
          </span>
        </div>
      </div>
      {m.title && <div style={{ fontSize: 12.5, fontWeight: 600, color: INK_TEXT, marginBottom: 3 }}>{m.title}</div>}
      {m.text && <div style={{ fontSize: 12, color: INK_TEXT, lineHeight: 1.45, marginBottom: 3 }}>{m.text.length > 400 ? `${m.text.slice(0, 400)}…` : m.text}</div>}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ fontSize: 10.5, color: MUTED, fontStyle: 'italic' }}>{m.reason}</div>
        {url && (
          <a href={url} target="_blank" rel="noreferrer" style={{ fontSize: 10.5, color: DEEP_TEAL, fontWeight: 600, flex: 'none', textDecoration: 'none' }}>
            View on Reddit →
          </a>
        )}
      </div>
    </div>
  )
}

export default function VoiceRedditMentions() {
  const [summary, setSummary] = useState(null)
  const [error, setError] = useState(null)

  const [expandedBrand, setExpandedBrand] = useState(null)
  const [brandThemeMix, setBrandThemeMix] = useState({}) // brand name -> themes[] | undefined (not yet fetched)
  const [complaintsByTheme, setComplaintsByTheme] = useState({}) // brand -> { `${theme}|${sentiment}` -> {loading, summary} }
  const [openComplaint, setOpenComplaint] = useState(null) // { brand, theme, sentiment } | null

  const [sampleBrand, setSampleBrand] = useState('')
  const [sampleSentiment, setSampleSentiment] = useState('')
  const [sampleAspect, setSampleAspect] = useState('')
  const [samples, setSamples] = useState(null)
  const mentionsSectionRef = useRef(null)

  // Reddit has no star rating, so the "which mentions count as negative"
  // filter here is overall sentiment instead (default 'negative') - the
  // closest Reddit-side equivalent to the Reviews page's 1/2/3-star filter.
  const [negativeSentimentFilter, setNegativeSentimentFilter] = useState('negative')
  const [negativeThemeMix, setNegativeThemeMix] = useState(null)

  useEffect(() => {
    api.voiceRedditSummary().then(setSummary).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    let cancelled = false
    setNegativeThemeMix(null)
    api.voiceRedditNegativeThemeMix(negativeSentimentFilter)
      .then((d) => { if (!cancelled) setNegativeThemeMix(d) })
      .catch(() => { if (!cancelled) setNegativeThemeMix([]) })
    return () => { cancelled = true }
  }, [negativeSentimentFilter])

  useEffect(() => {
    let cancelled = false
    setSamples(null)
    api.voiceRedditSample({ brand: sampleBrand || undefined, sentiment: sampleSentiment || undefined, aspect: sampleAspect || undefined, limit: 30 })
      .then((d) => { if (!cancelled) setSamples(d) })
      .catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [sampleBrand, sampleSentiment, sampleAspect])

  const toggleExpandBrand = (name) => {
    const next = expandedBrand === name ? null : name
    setExpandedBrand(next)
    if (next && brandThemeMix[next] === undefined) {
      setBrandThemeMix((prev) => ({ ...prev, [next]: null })) // null = loading
      api.voiceRedditThemeMix(next).then((d) => setBrandThemeMix((prev) => ({ ...prev, [next]: d }))).catch(() => setBrandThemeMix((prev) => ({ ...prev, [next]: [] })))
    }
  }

  const toggleComplaint = (brand, theme, sentiment) => {
    if (openComplaint?.brand === brand && openComplaint?.theme === theme && openComplaint?.sentiment === sentiment) {
      setOpenComplaint(null); return
    }
    setOpenComplaint({ brand, theme, sentiment })
    const key = `${theme}|${sentiment}`
    if (complaintsByTheme[brand]?.[key]) return
    setComplaintsByTheme((prev) => ({ ...prev, [brand]: { ...(prev[brand] || {}), [key]: { loading: true } } }))
    api.voiceRedditThemeComplaints(theme, brand, sentiment)
      .then((d) => setComplaintsByTheme((prev) => ({ ...prev, [brand]: { ...(prev[brand] || {}), [key]: { loading: false, summary: d.summary } } })))
      .catch(() => setComplaintsByTheme((prev) => ({ ...prev, [brand]: { ...(prev[brand] || {}), [key]: { loading: false, summary: null } } })))
  }

  const jumpToMentions = (brand, theme, sentiment) => {
    setSampleBrand(brand)
    setSampleSentiment(sentiment)
    setSampleAspect(theme)
    mentionsSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const brandOptions = useMemo(() => (summary || []).filter((b) => b.n_relevant > 0).map((b) => b.name), [summary])
  const totals = useMemo(() => {
    if (!summary) return null
    return summary.reduce((acc, b) => ({
      scraped: acc.scraped + b.n_scraped, relevant: acc.relevant + b.n_relevant,
    }), { scraped: 0, relevant: 0 })
  }, [summary])

  return (
    <div>
      <div style={{ fontSize: 11, color: MUTED, marginBottom: 14, maxWidth: '70ch' }}>
        Reddit posts and comments from a keyword search per brand, relevance- and sentiment-classified from the actual
        text (not just star ratings). {totals ? `${fmtNum(totals.relevant)} of ${fmtNum(totals.scraped)} scraped items judged genuinely about the brand.` : ''}
      </div>

      {error && <div style={{ padding: 12, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>}

      <Section title="Negative mentions by attribute" scope="Every brand at once, for comparison">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ fontSize: 10.5, color: MUTED, maxWidth: '52ch' }}>
            Among mentions with the sentiment selected, what % mention each attribute as a specific complaint. Same fixed attribute order for every brand.
          </div>
          <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            {['negative', 'neutral', 'positive'].map((s) => (
              <button key={s} onClick={() => setNegativeSentimentFilter(s)} style={pillStyle(negativeSentimentFilter === s)}>{s}</button>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <NegativeAttributeChart data={negativeThemeMix} />
        </div>
      </Section>

      <Section title="Mentions by brand" scope="Click a brand row to see what its mentions are specifically about">
        {summary === null ? (
          <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <div style={{ minWidth: 620 }}>
              <BrandTable
                rows={summary} expandedBrand={expandedBrand} onToggleExpand={toggleExpandBrand}
                brandThemeMix={brandThemeMix} complaintsByTheme={complaintsByTheme}
                openComplaint={openComplaint} onToggleComplaint={toggleComplaint} onSeeMentions={jumpToMentions}
              />
            </div>
          </div>
        )}
        <div style={{ display: 'flex', gap: 14, fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 8 }}>
          <span>Sentiment mix, left→right:</span>
          <span style={{ color: GREEN }}>■ positive</span>
          <span style={{ color: SLATE_400 }}>■ neutral</span>
          <span style={{ color: ROSE }}>■ negative</span>
        </div>
      </Section>

      <Section title="What people are saying" scope="Brand, aspect, and sentiment filters below are local to this list">
        <div ref={mentionsSectionRef} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <select
              value={sampleBrand} onChange={(e) => setSampleBrand(e.target.value)}
              style={selectStyle()}
            >
              <option value="">All brands</option>
              {brandOptions.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
            <select value={sampleAspect} onChange={(e) => setSampleAspect(e.target.value)} style={selectStyle()}>
              <option value="">All aspects</option>
              {Object.entries(ASPECT_LABELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
            {['', 'positive', 'neutral', 'negative'].map((s) => (
              <button key={s || 'all'} onClick={() => setSampleSentiment(s)} style={pillStyle(sampleSentiment === s)}>
                {s || 'All sentiment'}
              </button>
            ))}
          </div>
        </div>
        <div style={{ background: TEAL_WASH, borderRadius: 8, padding: '4px 14px', maxHeight: 480, overflowY: 'auto' }}>
          {samples === null ? (
            <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>Loading…</div>
          ) : samples.length === 0 ? (
            <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No mentions match this filter.</div>
          ) : (
            samples.map((m, i) => (
              <div key={i}>
                <MentionCard m={m} />
                {i < samples.length - 1 && <div style={{ height: 1, background: '#D8E6E7' }} />}
              </div>
            ))
          )}
        </div>
      </Section>
    </div>
  )
}
