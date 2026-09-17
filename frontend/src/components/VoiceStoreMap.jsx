import { useMemo } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import L from 'leaflet'
import { MapContainer, TileLayer, Marker, Tooltip, GeoJSON } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { DEEP_TEAL, GREEN, ROSE, SLATE_400, INK_TEXT, MONO, MUTED, fmtNum } from '../styles'

// react-simple-maps (used for the state/county/town choropleths) is pure
// SVG/vector - it has no concept of a raster basemap, so there's no way to
// "zoom in and see roads" with it. This innermost view is a genuinely
// different kind of map: real OpenStreetMap tiles via Leaflet (free, no API
// key). It also solves the "stores should spread apart on zoom" ask for
// free - Leaflet repositions DOM markers from real lat/lng on every zoom
// level while keeping each marker's own on-screen size constant, unlike an
// SVG group that scales markers up along with the geography.

function markerIcon(loc) {
  const isMavis = loc.family === 'mavis'
  const ringColor = isMavis
    ? (loc.delta === null || loc.delta === undefined ? SLATE_400 : loc.delta >= 0 ? GREEN : ROSE)
    : SLATE_400
  const html = renderToStaticMarkup(
    <div style={{ position: 'relative', width: 30, height: 40 }}>
      <div
        style={{
          width: 26, height: 26, borderRadius: '50%', background: '#FFFFFF',
          border: `2.5px solid ${ringColor}`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          overflow: 'hidden', boxShadow: '0 1px 3px rgba(15,20,24,.35)',
        }}
      >
        {loc.logo_url ? (
          <img src={loc.logo_url} width={18} height={18} style={{ objectFit: 'contain' }} />
        ) : (
          <span style={{ fontSize: 11, fontWeight: 700, color: INK_TEXT }}>{loc.brand?.[0] || '?'}</span>
        )}
      </div>
      <div
        style={{
          position: 'absolute', top: 27, left: '50%', transform: 'translateX(-50%)',
          fontSize: 9.5, fontWeight: 700, color: INK_TEXT, fontFamily: MONO, whiteSpace: 'nowrap',
          background: '#FFFFFF', padding: '0 4px', borderRadius: 3, boxShadow: '0 1px 2px rgba(15,20,24,.3)',
        }}
      >
        {loc.raw_rating != null ? loc.raw_rating.toFixed(1) : '—'}
      </div>
    </div>
  )
  return L.divIcon({ html, className: 'voice-marker-icon', iconSize: [30, 40], iconAnchor: [15, 13] })
}

function TooltipContent({ loc }) {
  const familyLabel = loc.family === 'mavis' ? 'Mavis' : 'Competitor'
  const address = [loc.street, loc.city, loc.zip].filter(Boolean).join(', ')
  return (
    <div style={{ fontSize: 11.5, lineHeight: 1.5, maxWidth: 230 }}>
      <div style={{ fontWeight: 700 }}>
        {loc.name} <span style={{ fontWeight: 400, color: MUTED }}>({loc.brand} · {familyLabel})</span>
      </div>
      <div style={{ color: MUTED }}>{address || 'no address on file'}</div>
      <div>Rating {loc.raw_rating != null ? loc.raw_rating.toFixed(2) : '—'} ({fmtNum(loc.review_count)} reviews)</div>
      {loc.family === 'mavis' && (
        loc.delta === null || loc.delta === undefined ? (
          <div style={{ color: MUTED }}>No competitors in this town to benchmark against</div>
        ) : (
          <>
            <div style={{ color: loc.delta >= 0 ? GREEN : ROSE, fontWeight: 600 }}>
              {loc.delta >= 0 ? '+' : ''}{loc.delta.toFixed(2)} stars vs. town competitor benchmark ({loc.comp_benchmark_rating?.toFixed(2)})
            </div>
            {loc.low_comparability && (
              <div style={{ color: MUTED }}>Low comparability - only {loc.n_competitors_in_ring} competitor(s) in this town</div>
            )}
          </>
        )
      )}
    </div>
  )
}

export default function VoiceStoreMap({ locations, boundaryGeometry, areaKey }) {
  const bounds = useMemo(
    () => (locations.length ? L.latLngBounds(locations.map((l) => [l.lat, l.lng])) : null),
    [locations]
  )
  const boundaryFeature = useMemo(
    () => (boundaryGeometry ? { type: 'Feature', properties: {}, geometry: boundaryGeometry } : null),
    [boundaryGeometry]
  )

  if (!bounds) {
    return <div style={{ textAlign: 'center', padding: 40, color: MUTED, fontSize: 12 }}>No mapped locations here.</div>
  }

  return (
    <div>
      <MapContainer
        key={areaKey}
        bounds={bounds}
        boundsOptions={{ padding: [40, 40], maxZoom: 17 }}
        style={{ width: '100%', height: 520, borderRadius: 10 }}
        scrollWheelZoom
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
        />
        {boundaryFeature && (
          <GeoJSON data={boundaryFeature} style={{ color: DEEP_TEAL, weight: 2, fillOpacity: 0.03, dashArray: '4 3' }} />
        )}
        {locations.map((loc) => (
          <Marker key={loc.location_id} position={[loc.lat, loc.lng]} icon={markerIcon(loc)}>
            <Tooltip direction="top" offset={[0, -16]}>
              <TooltipContent loc={loc} />
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8, fontSize: 10.5, color: MUTED, flexWrap: 'wrap' }}>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', border: `2.5px solid ${GREEN}`, marginRight: 5, verticalAlign: 'middle' }} /> Mavis, beating local competitors</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', border: `2.5px solid ${ROSE}`, marginRight: 5, verticalAlign: 'middle' }} /> Mavis, trailing local competitors</span>
        <span><span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', border: `2.5px solid ${SLATE_400}`, marginRight: 5, verticalAlign: 'middle' }} /> Competitor</span>
      </div>
    </div>
  )
}
