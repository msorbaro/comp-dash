import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { RowDivider } from './Widgets'
import {
  MUTED, INK_TEXT, SLATE_600, SLATE_400, SLATE_200, DEEP_TEAL, TEAL_700, TEAL_WASH,
  MONO, GREEN, ROSE, fmtNum,
} from '../styles'

function pillStyle(active) {
  return {
    fontSize: 10.5, fontWeight: active ? 600 : 500, padding: '5px 11px', borderRadius: 16,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
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

const BRAND_COLUMN_WIDTHS = ['2.4fr', '90px', '90px', '1.4fr']

function BrandTable({ rows }) {
  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: BRAND_COLUMN_WIDTHS.join(' '), gap: 12 }}>
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600 }}>BRAND</div>
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600, textAlign: 'right' }}>SCRAPED</div>
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600, textAlign: 'right' }}>RELEVANT</div>
        <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600 }}>SENTIMENT MIX</div>
      </div>
      <hr style={{ margin: '6px 0 4px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
      {rows.map((r) => (
        <div key={r.brand_id}>
          <div style={{ display: 'grid', gridTemplateColumns: BRAND_COLUMN_WIDTHS.join(' '), gap: 12, padding: '8px 0', fontSize: 12, background: r.mavis ? TEAL_WASH : 'transparent' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: r.mavis ? 600 : 400 }}>
              {r.logo && <img src={r.logo} alt="" width={14} height={14} style={{ borderRadius: 3, flex: 'none' }} onError={(e) => { e.currentTarget.style.display = 'none' }} />}
              {r.name}
              {r.mavis && <span style={{ color: TEAL_700, fontSize: 9.5, fontFamily: MONO, fontWeight: 600, paddingLeft: 6, letterSpacing: '.05em' }}>MAVIS</span>}
            </div>
            <div style={{ textAlign: 'right', fontFamily: MONO, color: MUTED }}>{fmtNum(r.n_scraped)}</div>
            <div style={{ textAlign: 'right', fontFamily: MONO, fontWeight: 600 }}>{fmtNum(r.n_relevant)}</div>
            <div><MixBar {...r} /></div>
          </div>
          <RowDivider />
        </div>
      ))}
    </div>
  )
}

function FavorBar({ n_favor_mavis, n_favor_competitor, n_neutral, mavisLabel, competitorLabel }) {
  const total = n_favor_mavis + n_favor_competitor + n_neutral
  if (total === 0) return null
  const pctMavis = (n_favor_mavis / total) * 100
  const pctComp = (n_favor_competitor / total) * 100
  const pctNeu = (n_neutral / total) * 100
  return (
    <div>
      <div style={{ display: 'flex', height: 14, borderRadius: 3, overflow: 'hidden' }}>
        {n_favor_mavis > 0 && <div style={{ width: `${pctMavis}%`, background: DEEP_TEAL }} title={`${mavisLabel}: ${n_favor_mavis}`} />}
        {n_neutral > 0 && <div style={{ width: `${pctNeu}%`, background: SLATE_400 }} title={`Neutral/tie: ${n_neutral}`} />}
        {n_favor_competitor > 0 && <div style={{ width: `${pctComp}%`, background: ROSE }} title={`${competitorLabel}: ${n_favor_competitor}`} />}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, fontFamily: MONO, color: MUTED, marginTop: 3 }}>
        <span style={{ color: DEEP_TEAL, fontWeight: 600 }}>{mavisLabel} {Math.round(pctMavis)}%</span>
        <span>{n_neutral} neutral</span>
        <span style={{ color: ROSE, fontWeight: 600 }}>{competitorLabel} {Math.round(pctComp)}%</span>
      </div>
    </div>
  )
}

function ComparisonLeaderboard({ rows }) {
  if (rows.length === 0) {
    return <div style={{ padding: 20, color: MUTED, fontSize: 12 }}>No comparison-themed mentions classified yet.</div>
  }
  return (
    <div>
      {rows.map((r, i) => (
        <div key={`${r.mavis_brand}|${r.competitor_brand}`} style={{ padding: '10px 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
            <div style={{ fontSize: 12.5 }}>
              <span style={{ fontWeight: 600 }}>{r.mavis_brand}</span>
              <span style={{ color: MUTED }}> vs </span>
              <span style={{ fontWeight: 600 }}>{r.competitor_brand}</span>
            </div>
            <div style={{ fontFamily: MONO, fontSize: 10.5, color: MUTED }}>{fmtNum(r.n_mentions)} mention{r.n_mentions === 1 ? '' : 's'}</div>
          </div>
          <FavorBar {...r} mavisLabel={r.mavis_brand} competitorLabel={r.competitor_brand} />
          {i < rows.length - 1 && <div style={{ height: 1, background: SLATE_200, marginTop: 10 }} />}
        </div>
      ))}
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
  const [comparisons, setComparisons] = useState(null)
  const [error, setError] = useState(null)
  const [sampleBrand, setSampleBrand] = useState('')
  const [sampleSentiment, setSampleSentiment] = useState('')
  const [samples, setSamples] = useState(null)

  useEffect(() => {
    api.voiceRedditSummary().then(setSummary).catch((e) => setError(e.message))
    api.voiceRedditComparisons().then(setComparisons).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    let cancelled = false
    setSamples(null)
    api.voiceRedditSample({ brand: sampleBrand || undefined, sentiment: sampleSentiment || undefined, limit: 30 })
      .then((d) => { if (!cancelled) setSamples(d) })
      .catch((e) => { if (!cancelled) setError(e.message) })
    return () => { cancelled = true }
  }, [sampleBrand, sampleSentiment])

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

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8 }}>Mentions by brand</div>
      {summary === null ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ minWidth: 620 }}>
            <BrandTable rows={summary} />
          </div>
        </div>
      )}
      <div style={{ display: 'flex', gap: 14, fontSize: 10.5, fontFamily: MONO, color: MUTED, marginTop: 8 }}>
        <span>Sentiment mix, left→right:</span>
        <span style={{ color: GREEN }}>■ positive</span>
        <span style={{ color: SLATE_400 }}>■ neutral</span>
        <span style={{ color: ROSE }}>■ negative</span>
      </div>

      <RowDivider />

      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>Head-to-head comparisons</div>
      <div style={{ fontSize: 10.5, color: MUTED, marginBottom: 8 }}>
        Every relevant mention classified as a direct Mavis-vs-competitor comparison, aggregated by pair.
      </div>
      {comparisons === null ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : (
        <ComparisonLeaderboard rows={comparisons} />
      )}

      <RowDivider />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>What people are saying</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select
            value={sampleBrand} onChange={(e) => setSampleBrand(e.target.value)}
            style={{ fontSize: 11, padding: '5px 8px', borderRadius: 8, border: `1px solid ${SLATE_200}`, fontFamily: 'Poppins, sans-serif', color: INK_TEXT }}
          >
            <option value="">All brands</option>
            {brandOptions.map((b) => <option key={b} value={b}>{b}</option>)}
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
    </div>
  )
}
