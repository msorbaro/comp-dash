import { ComposableMap, Geographies, Geography } from '@vnedyalk0v/react19-simple-maps'
import usTopology from 'us-atlas/states-10m.json'
import { divergingColor, SLATE_200, SLATE_400, MUTED, fmtNum } from '../styles'

function stateTooltip(s) {
  if (!s || !s.has_data) return s ? `${s.state_name}: no pilot data` : ''
  if (s.suppressed) {
    return `${s.state_name}: insufficient data\n${s.n_mavis_locations} Mavis locations, ${fmtNum(s.total_mavis_reviews)} reviews`
  }
  const sign = s.delta >= 0 ? '+' : ''
  return (
    `${s.state_name}: ${sign}${s.delta.toFixed(2)} stars vs. local competitors\n` +
    `Mavis ${s.mavis_rating.toFixed(2)} vs. competitors ${s.comp_rating.toFixed(2)}\n` +
    `${s.n_mavis_locations} Mavis locations, ${fmtNum(s.total_mavis_reviews)} reviews`
  )
}

export default function VoiceMap({ states, onSelectState }) {
  const byName = Object.fromEntries(states.map((s) => [s.state_name, s]))

  return (
    <div>
      <ComposableMap projection="geoAlbersUsa" style={{ width: '100%', height: 'auto' }}>
        <Geographies geography={usTopology}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const s = byName[geo.properties?.name]
              const visible = !!(s && s.has_data && !s.suppressed)
              const fill = visible ? divergingColor(s.delta) : SLATE_200
              return (
                <Geography
                  key={geo.id}
                  geography={geo}
                  title={stateTooltip(s)}
                  onClick={() => { if (visible) onSelectState(s.state) }}
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
      <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 18, marginTop: 8, fontSize: 10.5, color: MUTED }}>
        <Swatch color={divergingColor(-0.5)} label="-0.5 or worse" />
        <Swatch color="#FFFFFF" border={SLATE_400} label="even" />
        <Swatch color={divergingColor(0.5)} label="+0.5 or better" />
        <Swatch color={SLATE_200} label="insufficient data" />
      </div>
    </div>
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
