import { INK, TEAL, SLATE_400 } from '../styles'

const TABS = [
  { id: 'marketing', label: 'Competitive Marketing' },
  { id: 'voice', label: 'Customer Voice' },
]

export default function Header({ screen, onNav }) {
  return (
    <header
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 999,
        background: INK, height: 72, display: 'flex', alignItems: 'center',
        padding: '0 32px', borderBottom: '1px solid #253039', boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 'none' }}>
        <div style={{ width: 9, height: 9, borderRadius: '50%', background: TEAL, flex: 'none' }} />
        <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '.06em', color: '#FFFFFF', lineHeight: 1.25 }}>
          BRAND<br />SIGNAL
        </div>
        <div style={{ width: 1, alignSelf: 'stretch', background: '#334155', margin: '14px 0' }} />
        <div style={{ fontSize: 9.5, fontWeight: 600, letterSpacing: '.1em', color: SLATE_400, lineHeight: 1.5 }}>
          COMPETITIVE MARKETING<br />INTELLIGENCE
        </div>
      </div>
      <nav style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
        {TABS.map((t) => {
          const active = screen === t.id
          return (
            <button
              key={t.id}
              onClick={() => onNav(t.id)}
              style={{
                fontSize: 13.5, fontWeight: active ? 600 : 500, padding: '8px 14px', borderRadius: 7,
                cursor: 'pointer', border: 'none', whiteSpace: 'nowrap', fontFamily: 'Poppins, sans-serif',
                color: active ? INK : '#C7CED9', background: active ? TEAL : 'transparent',
              }}
            >
              {t.label}
            </button>
          )
        })}
      </nav>
    </header>
  )
}
