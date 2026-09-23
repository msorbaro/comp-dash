import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { RowDivider } from './Widgets'
import { MUTED, INK_TEXT, SLATE_600, SLATE_200, DEEP_TEAL, TEAL_WASH, TEAL_700, MONO, deltaBarStyle, fmtNum } from '../styles'

function fmtRating(v) {
  return v === null || v === undefined ? '—' : v.toFixed(2)
}

function fmtDelta(v) {
  if (v === null || v === undefined) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}`
}

function weightedAvg(items, valueKey, weightKey = 'review_count') {
  let sumWeight = 0, sumWeightedValue = 0
  for (const it of items) {
    const v = it[valueKey], w = it[weightKey]
    if (v === null || v === undefined || !w) continue
    sumWeight += w
    sumWeightedValue += w * v
  }
  return sumWeight ? sumWeightedValue / sumWeight : null
}

// A group of individual locations rolled up the same way state_delta /
// county_delta / town_delta are (see db/voice_metrics.sql): rating is the
// shrinkage-adjusted rating, benchmark/gap stay on the raw scale - the same
// three numbers shown at every level of the state-rooted table, just
// computed client-side here since these groups come from one brand's full
// location list rather than a precomputed view.
function rollupGroup(locs) {
  return {
    locs: locs.length,
    rating: weightedAvg(locs, 'adj_rating'),
    benchmark: weightedAvg(locs, 'comp_benchmark_rating'),
    gap: weightedAvg(locs, 'delta'),
  }
}

function groupBy(items, keyFn) {
  const map = new Map()
  for (const it of items) {
    const k = keyFn(it)
    if (!map.has(k)) map.set(k, [])
    map.get(k).push(it)
  }
  return map
}

// Groups sorted by their own rolled-up gap, best first - matches the
// default sort every other rollup in this app uses.
function sortedGroups(map) {
  return [...map.entries()].sort((a, b) => {
    const ga = weightedAvg(a[1], 'delta'), gb = weightedAvg(b[1], 'delta')
    if (ga === null) return 1
    if (gb === null) return -1
    return gb - ga
  })
}

const COLUMN_WIDTHS = ['1.7fr', '80px', '80px', '100px', '260px']

function Head() {
  const headCell = { fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600 }
  return (
    <>
      <div style={{ display: 'grid', gridTemplateColumns: COLUMN_WIDTHS.join(' '), gap: 12 }}>
        <div style={headCell}>BRAND / MARKET / STORE</div>
        <div style={{ ...headCell, textAlign: 'right' }}>STORES</div>
        <div style={{ ...headCell, textAlign: 'right' }}>RATING</div>
        <div style={{ ...headCell, textAlign: 'right' }}>BENCHMARK</div>
        <div style={headCell}>GAP</div>
      </div>
      <hr style={{ margin: '6px 0 4px', border: 'none', borderTop: `1px solid ${SLATE_200}` }} />
    </>
  )
}

function GapBar({ gap }) {
  if (gap === null || gap === undefined) return <span style={{ fontSize: 12, color: MUTED }}>—</span>
  const s = deltaBarStyle(gap, { scale: 1, center: 30 })
  return (
    <div style={{ position: 'relative', height: 14 }}>
      <div style={{ position: 'absolute', left: '30%', top: 0, bottom: 0, width: 1, background: SLATE_200 }} />
      <div style={{ position: 'absolute', top: 3, height: 8, borderRadius: 1, left: s.barLeft, width: s.barW, background: s.barColor }} />
      <div style={{ position: 'absolute', top: -1, lineHeight: '16px', fontFamily: MONO, fontSize: 11, fontWeight: 500, color: s.barColor, left: s.labelLeft, transform: s.labelTx, padding: s.labelPad, whiteSpace: 'nowrap' }}>
        {fmtDelta(gap)}
      </div>
    </div>
  )
}

const DEPTH_STYLE = [
  { indent: 0, weight: 600, size: 14, color: INK_TEXT },
  { indent: 16, weight: 500, size: 13, color: INK_TEXT },
  { indent: 32, weight: 400, size: 13, color: SLATE_600 },
  { indent: 48, weight: 400, size: 12.5, color: SLATE_600 },
  { indent: 64, weight: 400, size: 12, color: MUTED },
]

// A section divider distinguishing "this brand's own stores in the town"
// from "every other brand also in that town" - not a data row, just a
// label, so it carries no rating/benchmark/gap columns of its own.
function SectionHeader({ row }) {
  const d = DEPTH_STYLE[row.depth]
  return (
    <div style={{
      padding: '10px 0 4px', fontSize: 9.5, letterSpacing: '.08em', textTransform: 'uppercase',
      fontWeight: 600, color: SLATE_600, paddingLeft: d.indent + 14,
    }}>
      {row.label}
    </div>
  )
}

function TreeRow({ row }) {
  const d = DEPTH_STYLE[row.depth]
  if (row.header) return <SectionHeader row={row} />
  if (row.info) {
    return (
      <div style={{ padding: '7px 0', fontSize: 12, color: MUTED, paddingLeft: d.indent + 14 }}>{row.label}</div>
    )
  }
  return (
    <div
      onClick={row.onToggle}
      style={{
        display: 'grid', gridTemplateColumns: COLUMN_WIDTHS.join(' '), gap: 12,
        padding: '7px 0', fontSize: 12, cursor: row.onToggle ? 'pointer' : 'default',
        background: row.depth === 0 ? TEAL_WASH : row.own ? TEAL_WASH : 'transparent',
      }}
    >
      <div style={{ fontWeight: d.weight, fontSize: d.size, color: d.color }}>
        <span style={{ display: 'inline-block', width: d.indent }} />
        <span style={{ display: 'inline-block', width: 14, color: DEEP_TEAL, fontSize: 10 }}>
          {row.expandable ? (row.isOpen ? '▼' : '▶') : ''}
        </span>
        {row.label}
        {(row.depth === 0 || row.mavis) && (
          <span style={{ color: TEAL_700, fontSize: 10, fontFamily: MONO, fontWeight: 600, paddingLeft: 8, letterSpacing: '.05em' }}>MAVIS</span>
        )}
      </div>
      <div style={{ textAlign: 'right', fontFamily: MONO, color: MUTED }}>{row.locs === null ? '' : fmtNum(row.locs)}</div>
      <div style={{ textAlign: 'right', fontFamily: MONO, fontWeight: 600 }}>{fmtRating(row.rating)}</div>
      <div style={{ textAlign: 'right', fontFamily: MONO, color: MUTED }}>{fmtRating(row.benchmark)}</div>
      <div><GapBar gap={row.gap} /></div>
    </div>
  )
}

// A location's Google Business name is often just the brand name again
// (chain stores rarely have a distinct display name) - only show it
// separately when it actually differs.
function storeLabel(brand, loc) {
  const nameLabel = loc.name && loc.name !== brand ? `${brand} — ${loc.name}` : brand
  return `${nameLabel} · ${fmtNum(loc.review_count)} reviews`
}

export default function VoiceDrillTree({ states, source = 'google_maps' }) {
  const [brands, setBrands] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(() => new Set())
  const [locationsByBrand, setLocationsByBrand] = useState({})
  const [pending, setPending] = useState(() => new Set())
  const [failed, setFailed] = useState({})
  // Every rated location (any brand) in a given town, keyed by
  // state|county_fips|city - not brand-specific, so expanding the same
  // town under a second Mavis banner reuses what's already fetched.
  const [competitionByTown, setCompetitionByTown] = useState({})
  const [compPending, setCompPending] = useState(() => new Set())
  const [compFailed, setCompFailed] = useState({})

  // All of the per-brand/per-town caches above are keyed without `source` -
  // switching the ratings source invalidates every one of them, so reset
  // (and re-collapse) the whole tree rather than let a stale Google Maps
  // fetch sit under an Apple Maps label.
  useEffect(() => {
    setBrands(null); setError(null); setOpen(new Set())
    setLocationsByBrand({}); setPending(new Set()); setFailed({})
    setCompetitionByTown({}); setCompPending(new Set()); setCompFailed({})
    api.voiceMainBrandNationalSummary(source).then(setBrands).catch((e) => setError(e.message))
  }, [source])

  const stateName = useMemo(
    () => Object.fromEntries((states || []).map((s) => [s.state, s.state_name])),
    [states]
  )

  const toggleOpen = (key) => {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const loadBrandLocations = (brandId) => {
    if (locationsByBrand[brandId] || pending.has(brandId)) return
    setPending((prev) => new Set(prev).add(brandId))
    api.voiceMainBrandLocations(brandId, source)
      .then((locs) => setLocationsByBrand((prev) => ({ ...prev, [brandId]: locs })))
      .catch((e) => setFailed((prev) => ({ ...prev, [brandId]: e.message })))
      .finally(() => setPending((prev) => { const n = new Set(prev); n.delete(brandId); return n }))
  }

  const loadCompetition = (state, fips, city) => {
    const key = `${state}|${fips}|${city}`
    if (competitionByTown[key] || compPending.has(key)) return
    setCompPending((prev) => new Set(prev).add(key))
    api.voiceCountyLocations(state, fips, city, source)
      .then((locs) => setCompetitionByTown((prev) => ({ ...prev, [key]: locs })))
      .catch((e) => setCompFailed((prev) => ({ ...prev, [key]: e.message })))
      .finally(() => setCompPending((prev) => { const n = new Set(prev); n.delete(key); return n }))
  }

  const rows = []
  for (const b of brands || []) {
    const bKey = `brand:${b.brand_id}`
    const bOpen = open.has(bKey)
    rows.push({
      key: bKey, depth: 0, label: b.name, locs: b.n_mavis_locations,
      rating: b.mavis_rating, benchmark: b.comp_rating, gap: b.delta,
      expandable: true, isOpen: bOpen,
      onToggle: () => { toggleOpen(bKey); if (!bOpen) loadBrandLocations(b.brand_id) },
    })
    if (!bOpen) continue
    if (pending.has(b.brand_id)) { rows.push({ key: bKey + ':pending', depth: 1, info: true, label: 'Loading locations…' }); continue }
    if (failed[b.brand_id]) { rows.push({ key: bKey + ':err', depth: 1, info: true, label: `Couldn't load locations (${failed[b.brand_id]})` }); continue }
    const locs = locationsByBrand[b.brand_id] || []
    if (locs.length === 0) { rows.push({ key: bKey + ':empty', depth: 1, info: true, label: 'No rated locations' }); continue }

    for (const [state, stateLocs] of sortedGroups(groupBy(locs, (l) => l.state))) {
      const sKey = `state:${b.brand_id}|${state}`
      const sOpen = open.has(sKey)
      rows.push({ key: sKey, depth: 1, label: stateName[state] || state, expandable: true, isOpen: sOpen, onToggle: () => toggleOpen(sKey), ...rollupGroup(stateLocs) })
      if (!sOpen) continue

      for (const [fips, countyLocs] of sortedGroups(groupBy(stateLocs, (l) => l.county_fips))) {
        const cKey = `county:${b.brand_id}|${state}|${fips}`
        const cOpen = open.has(cKey)
        rows.push({ key: cKey, depth: 2, label: countyLocs[0].county_name, expandable: true, isOpen: cOpen, onToggle: () => toggleOpen(cKey), ...rollupGroup(countyLocs) })
        if (!cOpen) continue

        for (const [city, townLocs] of sortedGroups(groupBy(countyLocs, (l) => l.city))) {
          const tKey = `town:${b.brand_id}|${state}|${fips}|${city}`
          const tOpen = open.has(tKey)
          rows.push({
            key: tKey, depth: 3, label: city, expandable: true, isOpen: tOpen,
            onToggle: () => { toggleOpen(tKey); if (!tOpen) loadCompetition(state, fips, city) },
            ...rollupGroup(townLocs),
          })
          if (!tOpen) continue

          const compKey = `${state}|${fips}|${city}`
          const others = (competitionByTown[compKey] || []).filter((l) => l.brand !== b.name)
          const hasOthers = !compPending.has(compKey) && !compFailed[compKey] && others.length > 0

          rows.push({ key: tKey + ':own-header', depth: 4, header: true, label: `${b.name} in ${city}` })
          const sortedStores = [...townLocs].sort((a, b2) => (b2.raw_rating ?? -Infinity) - (a.raw_rating ?? -Infinity))
          for (const loc of sortedStores) {
            rows.push({
              key: tKey + ':' + loc.location_id, depth: 4,
              label: storeLabel(b.name, loc), own: true,
              locs: null, rating: loc.raw_rating, benchmark: loc.comp_benchmark_rating, gap: loc.delta,
              expandable: false,
            })
          }

          if (compPending.has(compKey)) {
            rows.push({ key: tKey + ':comp-pending', depth: 4, info: true, label: 'Loading nearby competition…' })
          } else if (compFailed[compKey]) {
            rows.push({ key: tKey + ':comp-err', depth: 4, info: true, label: `Couldn't load competition (${compFailed[compKey]})` })
          } else if (hasOthers) {
            rows.push({ key: tKey + ':comp-header', depth: 4, header: true, label: `Other locations in ${city}` })
            const sortedOthers = [...others].sort((a, b2) => (b2.raw_rating ?? -Infinity) - (a.raw_rating ?? -Infinity))
            for (const loc of sortedOthers) {
              rows.push({
                key: tKey + ':comp:' + loc.location_id, depth: 4,
                label: storeLabel(loc.brand, loc), mavis: loc.family === 'mavis',
                locs: null, rating: loc.raw_rating, benchmark: loc.comp_benchmark_rating, gap: loc.delta,
                expandable: false,
              })
            }
          }
        }
      }
    }
  }

  return (
    <div>
      <div style={{ fontSize: 11, color: MUTED, marginBottom: 14 }}>
        Mavis brand → state → county → town → store. Click any row to expand it in place.
      </div>
      {error ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>
      ) : brands === null ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>Loading…</div>
      ) : brands.length === 0 ? (
        <div style={{ padding: 30, color: MUTED, fontSize: 12 }}>No Mavis brands with pilot data.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <div style={{ minWidth: 820 }}>
            <Head />
            {rows.map((row) => (
              <div key={row.key}>
                <TreeRow row={row} />
                <RowDivider />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
