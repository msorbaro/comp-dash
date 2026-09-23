import { useEffect, useState } from 'react'
import { api } from '../api'
import { SectionNumber, PageSkeleton } from '../components/Widgets'
import VoiceMap from '../components/VoiceMap'
import VoiceDrillTree from '../components/VoiceDrillTree'
import VoiceRollup from '../components/VoiceRollup'
import VoiceHeadToHead from '../components/VoiceHeadToHead'
import VoiceReviewTrend from '../components/VoiceReviewTrend'
import VoiceRedditMentions from '../components/VoiceRedditMentions'
import { MUTED, SLATE_200, SLATE_600, DEEP_TEAL, TEAL_700, cardBase } from '../styles'

function pillStyle(active) {
  return {
    fontSize: 11.5, fontWeight: active ? 600 : 500, padding: '7px 13px', borderRadius: 20,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

// Views built on the ratings materialized-view chain (db/voice_metrics.sql) -
// these are the only ones the Google/Apple Maps source toggle applies to.
// Reviews and Reddit read entirely different tables (voice.reviews,
// voice.reddit_mentions), not rating_snapshots, so the toggle would be a
// no-op there and is hidden instead of shown-but-inert.
const SOURCE_FILTERED_VIEWS = new Set(['map', 'table', 'rollup', 'h2h'])

export default function Voice() {
  const [states, setStates] = useState(null)
  const [error, setError] = useState(null)
  const [view, setView] = useState('map')
  const [source, setSource] = useState('google_maps')

  const load = () => {
    setStates(null)
    setError(null)
    api.voiceStates(source).then(setStates).catch((e) => setError(e.message))
  }
  useEffect(load, [source])

  const activeCount = states ? states.filter((s) => s.has_data && !s.suppressed).length : 0

  return (
    <div>
      <SectionNumber num="06" title="Customer Voice" />
      <div style={{ ...cardBase, marginBottom: 14 }}>
        <div style={{ fontSize: 10, letterSpacing: '.15em', color: TEAL_700, fontWeight: 600 }}>CUSTOMER VOICE — PILOT</div>
        <h1 style={{ margin: '8px 0 0', fontSize: 28, fontWeight: 600 }}>Mavis review ratings vs. the local market</h1>
        <div style={{ fontSize: 12, color: MUTED, marginTop: 5, maxWidth: '70ch', lineHeight: 1.5 }}>
          Google Maps star ratings, Bayesian-shrunk per location, benchmarked against the average rating of every
          rated location — Mavis and competitor alike — in the same town. Pilot data only — {states ? `${activeCount} states with enough data to show` : 'loading…'}.
          Complaint theme analysis (from review text) is a later phase and not included here yet.
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginTop: 18 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={() => setView('map')} style={pillStyle(view === 'map')}>Map</button>
            <button onClick={() => setView('table')} style={pillStyle(view === 'table')}>Table</button>
            <button onClick={() => setView('rollup')} style={pillStyle(view === 'rollup')}>Rollup</button>
            <button onClick={() => setView('h2h')} style={pillStyle(view === 'h2h')}>Head to Head</button>
            <button onClick={() => setView('reviews')} style={pillStyle(view === 'reviews')}>Reviews</button>
            <button onClick={() => setView('reddit')} style={pillStyle(view === 'reddit')}>Reddit</button>
          </div>
          {SOURCE_FILTERED_VIEWS.has(view) && (
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 10, letterSpacing: '.08em', color: MUTED, fontWeight: 600, marginRight: 2 }}>RATINGS SOURCE</span>
              <button onClick={() => setSource('google_maps')} style={pillStyle(source === 'google_maps')}>Google Maps</button>
              <button onClick={() => setSource('apple_maps')} style={pillStyle(source === 'apple_maps')}>Apple Maps</button>
            </div>
          )}
        </div>
      </div>

      {error ? (
        <div style={{ padding: 40, color: MUTED }}>
          Couldn't load Customer Voice data ({error}).{' '}
          <span onClick={load} style={{ textDecoration: 'underline', cursor: 'pointer' }}>Try again</span>
        </div>
      ) : !states ? <PageSkeleton cards={1} gridItems={6} /> : (
        <div style={cardBase}>
          {view === 'map' ? (
            <VoiceMap states={states} source={source} />
          ) : view === 'table' ? (
            <VoiceDrillTree states={states} source={source} />
          ) : view === 'rollup' ? (
            <VoiceRollup states={states} source={source} />
          ) : view === 'h2h' ? (
            <VoiceHeadToHead states={states} source={source} />
          ) : view === 'reviews' ? (
            <VoiceReviewTrend states={states} />
          ) : (
            <VoiceRedditMentions />
          )}
        </div>
      )}
    </div>
  )
}
