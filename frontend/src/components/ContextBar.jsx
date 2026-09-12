import { ScopeChip } from './Widgets'
import { SURFACE, SLATE_200, MUTED, SLATE_600 } from '../styles'

export default function ContextBar({ scopeLabel, note, brands, brandValue, onBrandChange, crumb }) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        padding: '11px 16px', background: SURFACE, border: `1px solid ${SLATE_200}`,
        borderRadius: 10, marginBottom: 18,
      }}
    >
      <ScopeChip label={scopeLabel} />
      {brands && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          <div style={{ fontSize: 11, color: MUTED }}>Brand in focus</div>
          <select
            value={brandValue}
            onChange={(e) => onBrandChange(e.target.value)}
            style={{
              background: SURFACE, border: '1px solid #CBD5E1', borderRadius: 7, padding: '7px 10px',
              fontFamily: 'Poppins, sans-serif', fontSize: 12, fontWeight: 500, maxWidth: 320,
            }}
          >
            {brands.map((b) => (
              <option key={b.name} value={b.name}>{b.name} — {b.category}</option>
            ))}
          </select>
        </div>
      )}
      {crumb && !brands && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: MUTED }}>
          {crumb}
        </div>
      )}
      <div style={{ marginLeft: 'auto', fontSize: 11.5, color: SLATE_600, textAlign: 'right', maxWidth: 560, lineHeight: 1.4 }}>
        {note}
      </div>
    </div>
  )
}
