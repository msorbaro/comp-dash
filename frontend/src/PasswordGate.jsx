import { useState } from 'react'

// The app shell always loads - this just blocks it from rendering until the
// backend has accepted the password and set its auth cookie. Real
// enforcement lives server-side (every /api/* call requires that cookie);
// this component is only the UI for getting it. sessionStorage is purely a
// convenience so a reload within the same tab doesn't re-prompt - it is not
// itself a security boundary.
export default function PasswordGate({ children }) {
  const [authed, setAuthed] = useState(() => sessionStorage.getItem('bs_authed') === '1')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (authed) return children

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      if (res.ok) {
        sessionStorage.setItem('bs_authed', '1')
        setAuthed(true)
      } else {
        setError('Incorrect password')
      }
    } catch {
      setError('Something went wrong - try again')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: '#F6F8FA', fontFamily: 'Poppins, system-ui, sans-serif',
    }}>
      <form onSubmit={submit} style={{
        background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: 12,
        padding: '32px 34px', width: 320, textAlign: 'center', boxShadow: '0 1px 3px rgba(15,20,24,.06)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 4 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22B8C4' }} />
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1A1F26' }}>Brand Signal</div>
        </div>
        <div style={{ fontSize: 12, color: '#6B7885', marginBottom: 20 }}>Enter the password to continue</div>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          style={{
            width: '100%', boxSizing: 'border-box', padding: '10px 12px', fontSize: 13,
            border: '1px solid #E2E8F0', borderRadius: 7, marginBottom: 12, fontFamily: 'inherit',
          }}
        />
        {error && <div style={{ fontSize: 11.5, color: '#E11D48', marginBottom: 10 }}>{error}</div>}
        <button
          type="submit"
          disabled={loading || !password}
          style={{
            width: '100%', padding: '10px 0', fontSize: 13, fontWeight: 600, color: '#FFFFFF',
            background: loading || !password ? '#5A8489' : '#0B4F55', border: 'none', borderRadius: 7,
            cursor: loading || !password ? 'default' : 'pointer', fontFamily: 'inherit',
          }}
        >
          {loading ? 'Checking…' : 'Enter'}
        </button>
      </form>
    </div>
  )
}
