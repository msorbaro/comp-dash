import { useEffect, useMemo, useState } from 'react'
import { geoMercator } from 'd3-geo'
import { feature } from 'topojson-client'
import { ComposableMap, Geographies, Geography, Marker } from '@vnedyalk0v/react19-simple-maps'
import usStatesTopology from 'us-atlas/states-10m.json'
import usCountiesTopology from 'us-atlas/counties-10m.json'
import { api } from '../api'
import { divergingColor, SLATE_200, SLATE_400, MUTED, INK_TEXT, TEAL_700, fmtNum } from '../styles'

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

export default function VoiceMap({ states }) {
  const [selectedState, setSelectedState] = useState(null) // { code, name }
  const [selectedCounty, setSelectedCounty] = useState(null) // { fips, name }
  const [counties, setCounties] = useState(null)
  const [stores, setStores] = useState(null)
  const [error, setError] = useState(null)

  const mode = selectedCounty ? 'stores' : selectedState ? 'county' : 'us'

  useEffect(() => {
    if (!selectedState) return
    setCounties(null); setError(null)
    api.voiceCounties(selectedState.code).then(setCounties).catch((e) => setError(e.message))
  }, [selectedState])

  useEffect(() => {
    if (!selectedState || !selectedCounty) return
    setStores(null); setError(null)
    api.voiceStores(selectedState.code, undefined, selectedCounty.fips).then(setStores).catch((e) => setError(e.message))
  }, [selectedState, selectedCounty])

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

  const crumbs = [{ label: 'All states', onClick: mode !== 'us' ? () => { setSelectedState(null); setSelectedCounty(null) } : null }]
  if (selectedState) crumbs.push({ label: selectedState.name, onClick: mode === 'stores' ? () => setSelectedCounty(null) : null })
  if (selectedCounty) crumbs.push({ label: `${selectedCounty.name} County`, onClick: null })

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
                    title={areaTooltip(geo.properties?.name, s)}
                    onClick={() => { if (visible) setSelectedState({ code: s.state, name: s.state_name }) }}
                    style={{
                      default: { fill, stroke: '#FFFFFF', strokeWidth: 0.75, outline: 'none', cursor: visible ? 'pointer' : 'default' },
                      hover: { fill, stroke: '#FFFFFF', strokeWidth: 1.25, outline: 'none', opacity: visible ? 0.82 : 1 },
                      pressed: { fill, stroke: '#FFFFFF', strokeWidth: 1.25, outline: 'none' },
                    }}
                  />
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
                    title={areaTooltip(geo.properties?.name ? `${geo.properties.name} County` : geo.id, c)}
                    onClick={() => { if (c) setSelectedCounty({ fips: geo.id, name: geo.properties?.name || c.county_name }) }}
                    style={{
                      default: { fill, stroke: '#FFFFFF', strokeWidth: 0.75, outline: 'none', cursor: c ? 'pointer' : 'default' },
                      hover: { fill, stroke: '#FFFFFF', strokeWidth: 1.25, outline: 'none', opacity: c ? 0.82 : 1 },
                      pressed: { fill, stroke: '#FFFFFF', strokeWidth: 1.25, outline: 'none' },
                    }}
                  />
                )
              })
            }
          </Geographies>
        </ComposableMap>
      )}

      {mode === 'stores' && (
        <ComposableMap projection={storesProjection || 'geoMercator'} width={WIDTH} height={HEIGHT} style={{ width: '100%', height: 'auto' }}>
          <Geographies geography={selectedCountyFeatureCollection}>
            {({ geographies }) =>
              geographies.map((geo) => (
                <Geography
                  key={geo.id}
                  geography={geo}
                  style={{ default: { fill: '#F6F8FA', stroke: SLATE_400, strokeWidth: 1, outline: 'none' } }}
                />
              ))
            }
          </Geographies>
          {(stores || []).map((store, i) => (
            <Marker key={i} coordinates={[store.lng, store.lat]}>
              <circle r={7} fill={divergingColor(store.delta)} stroke="#FFFFFF" strokeWidth={1.5}>
                <title>
                  {`${store.name} (${store.brand})\n` +
                    `Rating ${store.mavis_adj_rating?.toFixed(2) ?? '—'} vs. competitor benchmark ${store.comp_benchmark_rating?.toFixed(2) ?? '—'}\n` +
                    `Delta ${store.delta >= 0 ? '+' : ''}${store.delta?.toFixed(2) ?? '—'} · ${store.mavis_review_count} reviews\n` +
                    (store.low_comparability ? `Low comparability - only ${store.n_competitors_in_ring} competitor(s) within 15mi` : `${store.n_competitors_in_ring} competitors within 15mi`)}
                </title>
              </circle>
            </Marker>
          ))}
        </ComposableMap>
      )}

      {mode === 'stores' && !error && stores === null && (
        <div style={{ textAlign: 'center', padding: 12, color: MUTED, fontSize: 12 }}>Loading stores…</div>
      )}
      {mode === 'county' && !error && counties === null && (
        <div style={{ textAlign: 'center', padding: 12, color: MUTED, fontSize: 12 }}>Loading counties…</div>
      )}

      <Legend grayLabel={mode === 'stores' ? 'no competitors within 15mi' : 'insufficient data'} />
    </div>
  )
}
