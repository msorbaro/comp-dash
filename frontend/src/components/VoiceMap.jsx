import { useEffect, useMemo, useState } from 'react'
import { geoMercator, geoBounds } from 'd3-geo'
import { feature } from 'topojson-client'
import { ComposableMap, Geographies, Geography, ZoomableGroup } from '@vnedyalk0v/react19-simple-maps'
import usStatesTopology from 'us-atlas/states-10m.json'
import usCountiesTopology from 'us-atlas/counties-10m.json'
import { api } from '../api'
import VoiceStoreMap from './VoiceStoreMap'
import { divergingColor, SLATE_200, SLATE_400, SLATE_600, MUTED, INK_TEXT, TEAL_700, DEEP_TEAL, GREEN, ROSE, MONO, fmtNum } from '../styles'

// Decoded once at module load (not per-render) - topojson-client turns the
// arc-encoded topology into plain GeoJSON with real [lng,lat] coordinates,
// which both the county-filtering and the zoom-to-fit projection below need.
const COUNTY_FEATURES = feature(usCountiesTopology, usCountiesTopology.objects.counties).features
const STATE_FIPS_BY_NAME = Object.fromEntries(
  feature(usStatesTopology, usStatesTopology.objects.states).features.map((f) => [f.properties.name, f.id])
)

const WIDTH = 900
const HEIGHT = 520

// A projection fit to just the given features' bounding box, for the
// county-level and store-marker views - the national map's fixed
// geoAlbersUsa projection can't be zoomed into a single state or county.
function fitProjection(features, padding = 24) {
  const fc = { type: 'FeatureCollection', features }
  return geoMercator().fitExtent([[padding, padding], [WIDTH - padding, HEIGHT - padding]], fc)
}

// ZoomableGroup's `center` is a geographic [lng,lat] point (it runs the
// projection on it internally to compute the pixel offset), not a pixel
// coordinate - the bounding-box midpoint of whatever fitProjection() just
// fit the view to keeps the initial zoomed-in view visually unchanged
// before the user actually drags/scrolls.
function centroidOf(feature) {
  const [[minLng, minLat], [maxLng, maxLat]] = geoBounds(feature)
  return [(minLng + maxLng) / 2, (minLat + maxLat) / 2]
}

// Geography needs a concrete style object for every interaction state it can
// land in (default/hover/pressed/focused) - it reads style[state] directly
// with no fallback, so a missing key (e.g. no `focused` variant) means no
// style at all gets applied and the shape renders with SVG's bare default
// fill: black. Clicking a shape focuses it (it's keyboard-focusable), so
// "focused" isn't a rare state to skip - always provide all four.
function regionStyle(fill, clickable) {
  const base = { fill, stroke: '#FFFFFF', outline: 'none' }
  return {
    default: { ...base, strokeWidth: 0.75, cursor: clickable ? 'pointer' : 'default' },
    hover: { ...base, strokeWidth: 1.25, opacity: clickable ? 0.82 : 1, cursor: clickable ? 'pointer' : 'default' },
    pressed: { ...base, strokeWidth: 1.25 },
    focused: { ...base, strokeWidth: 0.75, cursor: clickable ? 'pointer' : 'default' },
  }
}

function comparabilityNote(r) {
  if (!r.n_low_comparability_locations) return ''
  const n = r.n_low_comparability_locations
  return `\n${n} store${n === 1 ? '' : 's'} w/ <3 nearby competitors`
}

function areaTooltip(label, r) {
  if (!r) return label
  if (r.suppressed) return `${label}: insufficient data`
  const sign = r.delta >= 0 ? '+' : ''
  return (
    `${label}: ${sign}${r.delta.toFixed(2)} stars vs. local competitors\n` +
    `Mavis ${r.mavis_rating.toFixed(2)} vs. competitors ${r.comp_rating.toFixed(2)}\n` +
    `${r.n_mavis_locations} Mavis locations, ${fmtNum(r.total_mavis_reviews)} reviews${comparabilityNote(r)}`
  )
}

function Swatch({ color, label, border }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
      <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, background: color, border: border ? `1px solid ${border}` : 'none' }} />
      {label}
    </span>
  )
}

function Legend({ grayLabel }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 18, marginTop: 8, fontSize: 10.5, color: MUTED }}>
      <Swatch color={divergingColor(-0.5)} label="-0.5 or worse" />
      <Swatch color="#FFFFFF" border={SLATE_400} label="even" />
      <Swatch color={divergingColor(0.5)} label="+0.5 or better" />
      <Swatch color={SLATE_200} label={grayLabel} />
    </div>
  )
}

function Crumbs({ items }) {
  return (
    <div style={{ fontSize: 11, color: MUTED, marginBottom: 10 }}>
      {items.map((c, i) => (
        <span key={i}>
          {i > 0 && <span style={{ margin: '0 6px' }}>›</span>}
          {c.onClick ? (
            <span onClick={c.onClick} style={{ cursor: 'pointer', textDecoration: 'underline', color: TEAL_700 }}>{c.label}</span>
          ) : (
            <span style={{ fontWeight: 600, color: INK_TEXT }}>{c.label}</span>
          )}
        </span>
      ))}
    </div>
  )
}

function fmtTownStatus(t) {
  if (t.suppressed) return 'insufficient data'
  const sign = t.delta >= 0 ? '+' : ''
  return `${sign}${t.delta.toFixed(2)} vs. competitors${comparabilityNote(t)}`
}

// Fallback for the minority of towns with no matching Census place polygon
// (see scripts/backfill_town_boundaries.py) - still selectable, just not
// drawn as a shape on the map above.
function UnmappedTownList({ towns, onSelectTown }) {
  if (!towns.length) return null
  return (
    <div style={{ maxWidth: 560, margin: '10px auto 0' }}>
      <div style={{ fontSize: 9.5, letterSpacing: '.1em', color: MUTED, fontWeight: 600, marginBottom: 4 }}>
        NO MAPPED BOUNDARY FOR THESE TOWNS
      </div>
      {towns.map((t) => (
        <div
          key={t.city}
          onClick={() => onSelectTown(t.city)}
          style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 10px',
            borderBottom: `1px solid ${SLATE_200}`, cursor: 'pointer', fontSize: 12,
          }}
        >
          <span style={{ color: INK_TEXT }}>{t.city}</span>
          <span style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
            <span style={{ fontSize: 10, color: SLATE_600 }}>{t.n_mavis_locations} Mavis loc.</span>
            <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: t.suppressed ? MUTED : (t.delta >= 0 ? GREEN : ROSE) }}>
              {fmtTownStatus(t)}
            </span>
          </span>
        </div>
      ))}
    </div>
  )
}

export default function VoiceMap({ states }) {
  const [selectedState, setSelectedState] = useState(null) // { code, name }
  const [selectedCounty, setSelectedCounty] = useState(null) // { fips, name }
  const [townChoice, setTownChoice] = useState(null) // null = still choosing, { city: string|null }
  const [counties, setCounties] = useState(null)
  const [towns, setTowns] = useState(null)
  const [locations, setLocations] = useState(null)
  const [error, setError] = useState(null)

  const mode = !selectedState ? 'us' : !selectedCounty ? 'county' : townChoice === null ? 'town' : 'stores'

  const chooseState = (s) => { setSelectedState(s); setSelectedCounty(null); setTownChoice(null) }
  const chooseCounty = (c) => { setSelectedCounty(c); setTownChoice(null) }

  useEffect(() => {
    if (!selectedState) return
    setCounties(null); setError(null)
    api.voiceCounties(selectedState.code).then(setCounties).catch((e) => setError(e.message))
  }, [selectedState])

  useEffect(() => {
    if (!selectedState || !selectedCounty) return
    setTowns(null); setError(null)
    api.voiceCountyTowns(selectedState.code, selectedCounty.fips).then(setTowns).catch((e) => setError(e.message))
  }, [selectedState, selectedCounty])

  useEffect(() => {
    if (!selectedState || !selectedCounty || townChoice === null) return
    setLocations(null); setError(null)
    api.voiceCountyLocations(selectedState.code, selectedCounty.fips, townChoice.city || undefined)
      .then(setLocations).catch((e) => setError(e.message))
  }, [selectedState, selectedCounty, townChoice])

  const byStateName = useMemo(() => Object.fromEntries(states.map((s) => [s.state_name, s])), [states])
  const byCountyFips = useMemo(() => Object.fromEntries((counties || []).map((c) => [c.county_fips, c])), [counties])

  const stateFips = selectedState ? STATE_FIPS_BY_NAME[selectedState.name] : null
  const countyFeaturesForState = useMemo(
    () => (stateFips ? COUNTY_FEATURES.filter((f) => f.id.startsWith(stateFips)) : []),
    [stateFips]
  )
  const countyProjection = useMemo(
    () => (countyFeaturesForState.length ? fitProjection(countyFeaturesForState) : null),
    [countyFeaturesForState]
  )
  const selectedCountyFeature = useMemo(
    () => (selectedCounty ? COUNTY_FEATURES.find((f) => f.id === selectedCounty.fips) : null),
    [selectedCounty]
  )
  const storesProjection = useMemo(
    () => (selectedCountyFeature ? fitProjection([selectedCountyFeature], 40) : null),
    [selectedCountyFeature]
  )

  // Geography (below) only renders correctly for objects that have come out
  // of Geographies's own render-prop - this library pre-computes each
  // feature's SVG path there and Geography just reads it off, rather than
  // computing it itself from context. Feeding Geography a raw, manually
  // decoded feature (no Geographies wrapper) renders an empty/path-less
  // shape - so both of these go through Geographies, just fed a pre-filtered
  // FeatureCollection instead of the full nationwide topology.
  const countyFeatureCollection = useMemo(
    () => ({ type: 'FeatureCollection', features: countyFeaturesForState }),
    [countyFeaturesForState]
  )
  const selectedCountyFeatureCollection = useMemo(
    () => ({ type: 'FeatureCollection', features: selectedCountyFeature ? [selectedCountyFeature] : [] }),
    [selectedCountyFeature]
  )

  // Towns with a real Census place polygon (see scripts/backfill_town_boundaries.py)
  // render as their own colored shapes, same as counties; the rest fall
  // back to a plain clickable list below the map.
  const mappedTowns = useMemo(() => (towns || []).filter((t) => t.geometry), [towns])
  const unmappedTowns = useMemo(() => (towns || []).filter((t) => !t.geometry), [towns])
  const townFeatureCollection = useMemo(
    () => ({
      type: 'FeatureCollection',
      features: mappedTowns.map((t) => ({ type: 'Feature', id: t.city, properties: { name: t.city }, geometry: t.geometry })),
    }),
    [mappedTowns]
  )
  const byTownCity = useMemo(() => Object.fromEntries((towns || []).map((t) => [t.city, t])), [towns])

  // Once a specific town is chosen, zoom to its own polygon instead of
  // staying at the whole county's zoom level - "zoom into a high level map
  // of the town" per spec. Falls back to the county's own outline/zoom for
  // "view all" or for a town with no mapped boundary.
  const selectedTownFeature = useMemo(() => {
    if (!townChoice?.city) return null
    const t = byTownCity[townChoice.city]
    return t?.geometry ? { type: 'Feature', id: t.city, properties: { name: t.city }, geometry: t.geometry } : null
  }, [townChoice, byTownCity])
  // Outline shown under the real street map (VoiceStoreMap) - the chosen
  // town's own boundary when it has one, else the whole county's.
  const boundaryGeometry = selectedTownFeature?.geometry || selectedCountyFeature?.geometry || null
  const townCenter = useMemo(
    () => centroidOf(selectedCountyFeature || { type: 'Point', coordinates: [-98, 39] }),
    [selectedCountyFeature]
  )

  const crumbs = [{ label: 'All states', onClick: mode !== 'us' ? () => chooseState(null) : null }]
  if (selectedState) crumbs.push({ label: selectedState.name, onClick: mode !== 'county' ? () => chooseCounty(null) : null })
  if (selectedCounty) crumbs.push({ label: `${selectedCounty.name} County`, onClick: mode === 'stores' ? () => setTownChoice(null) : null })
  if (townChoice?.city) crumbs.push({ label: townChoice.city, onClick: null })

  return (
    <div>
      {mode !== 'us' && <Crumbs items={crumbs} />}

      {error && <div style={{ padding: 12, color: MUTED, fontSize: 12 }}>Couldn't load this view ({error}).</div>}

      {mode === 'us' && (
        <ComposableMap projection="geoAlbersUsa" width={WIDTH} height={HEIGHT} style={{ width: '100%', height: 'auto' }}>
          <Geographies geography={usStatesTopology}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const s = byStateName[geo.properties?.name]
                const visible = !!(s && s.has_data && !s.suppressed)
                const fill = visible ? divergingColor(s.delta) : SLATE_200
                return (
                  <Geography
                    key={geo.id}
                    geography={geo}
                    onClick={() => { if (visible) chooseState({ code: s.state, name: s.state_name }) }}
                    style={regionStyle(fill, visible)}
                  >
                    <title>{areaTooltip(geo.properties?.name, s)}</title>
                  </Geography>
                )
              })
            }
          </Geographies>
        </ComposableMap>
      )}

      {mode === 'county' && countyProjection && (
        <ComposableMap projection={countyProjection} width={WIDTH} height={HEIGHT} style={{ width: '100%', height: 'auto' }}>
          <Geographies geography={countyFeatureCollection}>
            {({ geographies }) =>
              geographies.map((geo) => {
                const c = byCountyFips[geo.id]
                const visible = !!(c && !c.suppressed)
                const fill = visible ? divergingColor(c.delta) : SLATE_200
                return (
                  <Geography
                    key={geo.id}
                    geography={geo}
                    onClick={() => { if (c) chooseCounty({ fips: geo.id, name: geo.properties?.name || c.county_name }) }}
                    style={regionStyle(fill, !!c)}
                  >
                    <title>{areaTooltip(geo.properties?.name ? `${geo.properties.name} County` : geo.id, c)}</title>
                  </Geography>
                )
              })
            }
          </Geographies>
        </ComposableMap>
      )}

      {mode === 'town' && (
        <>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 6 }}>
            <span
              onClick={() => setTownChoice({ city: null })}
              style={{ fontSize: 11, fontWeight: 600, color: DEEP_TEAL, cursor: 'pointer', textDecoration: 'underline' }}
            >
              View every location in the county →
            </span>
          </div>
          <ComposableMap projection={storesProjection || 'geoMercator'} width={WIDTH} height={HEIGHT} style={{ width: '100%', height: 'auto' }}>
            <ZoomableGroup center={townCenter} zoom={1} minZoom={1} maxZoom={12}>
              {/* The whole county, in gray, drawn first so any part of it not
                  covered by a town below still reads as "part of the county,
                  just not in the analysis" rather than empty white space. */}
              <Geographies geography={selectedCountyFeatureCollection}>
                {({ geographies }) =>
                  geographies.map((geo) => (
                    <Geography key={geo.id} geography={geo} style={regionStyle(SLATE_200, false)} />
                  ))
                }
              </Geographies>
              <Geographies geography={townFeatureCollection}>
                {({ geographies }) =>
                  geographies.map((geo) => {
                    const t = byTownCity[geo.properties?.name]
                    const visible = !!(t && !t.suppressed)
                    const fill = visible ? divergingColor(t.delta) : SLATE_200
                    return (
                      <Geography
                        key={geo.id}
                        geography={geo}
                        onClick={() => setTownChoice({ city: geo.properties?.name })}
                        style={regionStyle(fill, true)}
                      >
                        <title>{areaTooltip(geo.properties?.name, t)}</title>
                      </Geography>
                    )
                  })
                }
              </Geographies>
            </ZoomableGroup>
          </ComposableMap>
          {!error && towns === null && (
            <div style={{ textAlign: 'center', padding: 12, color: MUTED, fontSize: 12 }}>Loading towns…</div>
          )}
          {towns && <UnmappedTownList towns={unmappedTowns} onSelectTown={(city) => setTownChoice({ city })} />}
          {towns && <Legend grayLabel="insufficient data / not in analysis" />}
          {towns && (
            <div style={{ textAlign: 'center', fontSize: 10, color: MUTED, marginTop: 4 }}>Scroll to zoom, drag to pan</div>
          )}
        </>
      )}

      {mode === 'stores' && !error && locations === null && (
        <div style={{ textAlign: 'center', padding: 12, color: MUTED, fontSize: 12 }}>Loading locations…</div>
      )}
      {mode === 'stores' && locations !== null && (
        <VoiceStoreMap
          locations={locations}
          boundaryGeometry={boundaryGeometry}
          areaKey={`${selectedCounty?.fips}-${townChoice?.city || 'all'}`}
        />
      )}
      {mode === 'county' && !error && counties === null && (
        <div style={{ textAlign: 'center', padding: 12, color: MUTED, fontSize: 12 }}>Loading counties…</div>
      )}

      {(mode === 'us' || mode === 'county') && <Legend grayLabel="insufficient data" />}
    </div>
  )
}
