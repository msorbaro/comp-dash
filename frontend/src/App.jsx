import { useEffect, useState } from 'react'
import Header from './components/Header'
import CompetitiveMarketing from './screens/CompetitiveMarketing'
import Voice from './screens/Voice'
import { Shimmer } from './components/Widgets'
import { api } from './api'
import { CANVAS, MUTED } from './styles'

// Plain URL <-> screen sync via the History API - no router library, matching
// this app's dependency-light convention. Landscape/Brand/Category/Head to
// head used to be four separate top-level screens with their own paths;
// they're now one 'marketing' screen with an internal pill-switched `view`
// (see CompetitiveMarketing.jsx), so all of their old paths collapse to '/'
// - kept mapped here so old bookmarks/links still land on the right screen.
const PATH_FOR_SCREEN = { marketing: '/', voice: '/voice' }
const SCREEN_FOR_PATH = { '/': 'marketing', '/brand': 'marketing', '/category': 'marketing', '/compare': 'marketing', '/voice': 'voice' }

export default function App() {
  const [meta, setMeta] = useState(null)
  const [screen, setScreen] = useState(() => SCREEN_FOR_PATH[window.location.pathname] || 'marketing')
  const [marketingView, setMarketingView] = useState('landscape')
  const [brand, setBrand] = useState(null)
  const [channelId, setChannelId] = useState(null)
  const [channelTypeFilter, setChannelTypeFilter] = useState(null)
  const [category, setCategory] = useState(null)
  const [compareA, setCompareA] = useState(null)
  const [compareB, setCompareB] = useState(null)

  useEffect(() => {
    api.meta().then((m) => {
      setMeta(m)
      const firstBrand = m.brands[0]?.name
      setBrand(firstBrand)
      setCategory(m.categories[0]?.name)
      setCompareA(firstBrand)
      setCompareB(m.brands[1]?.name)
    })
  }, [])

  // Back/forward buttons - bring the screen back in sync with whatever path
  // the browser just navigated to (goto()/openChannel() below handle the
  // other direction, screen change -> pushState).
  useEffect(() => {
    const onPopState = () => setScreen(SCREEN_FOR_PATH[window.location.pathname] || 'marketing')
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  if (!meta) return (
    <div style={{ minHeight: '100vh', background: CANVAS, padding: '92px 32px 80px' }}>
      <div style={{ maxWidth: 1440, margin: '0 auto' }}>
        <Shimmer width={200} height={12} radius={4} style={{ marginBottom: 12 }} />
        <Shimmer width={480} height={28} radius={6} />
      </div>
    </div>
  )

  const goto = (nextScreen) => {
    setScreen(nextScreen)
    const path = PATH_FOR_SCREEN[nextScreen] || '/'
    if (window.location.pathname !== path) window.history.pushState({}, '', path)
    window.scrollTo(0, 0)
  }
  // Switches the pill sub-view within the Competitive Marketing tab
  // (Landscape/Brand/Category/Head to head). Channel is a sub-view of Brand
  // reached by clicking a channel card, not one of these pills, so leaving
  // or re-entering the Brand pill always resets back out of it.
  const switchMarketingView = (nextView) => {
    setChannelId(null)
    // Head to head always opens with the brand currently in focus as Side A,
    // so jumping there from anywhere else is a sensible starting comparison.
    if (nextView === 'compare' && marketingView !== 'compare') setCompareA(brand)
    setMarketingView(nextView)
    goto('marketing')
  }
  const openBrand = (name) => { setBrand(name); switchMarketingView('brand') }
  const openChannel = (id, typeFilter = null) => {
    setChannelId(id); setChannelTypeFilter(typeFilter)
    window.scrollTo(0, 0)
  }
  const closeChannel = () => setChannelId(null)
  const openCategory = (name) => { setCategory(name); switchMarketingView('category') }

  return (
    <div style={{ minHeight: '100vh', background: CANVAS, fontFamily: 'Poppins, system-ui, sans-serif', fontSize: 13, color: '#1A1F26' }}>
      <Header screen={screen} onNav={goto} />
      <main style={{ maxWidth: 1440, margin: '0 auto', padding: '92px 32px 80px' }}>
        {screen === 'marketing' && (
          <CompetitiveMarketing
            meta={meta} view={marketingView} onViewChange={switchMarketingView}
            brand={brand} onBrandChange={openBrand}
            channelId={channelId} channelTypeFilter={channelTypeFilter}
            onOpenChannel={openChannel} onCloseChannel={closeChannel}
            category={category} onCategoryChange={setCategory} onOpenCategory={openCategory}
            compareA={compareA} compareB={compareB}
            onCompareAChange={setCompareA} onCompareBChange={setCompareB}
          />
        )}
        {screen === 'voice' && <Voice />}
        <div style={{ marginTop: 28, paddingTop: 16, borderTop: '1px solid #E2E8F0', display: 'flex', justifyContent: 'space-between', fontSize: 10, color: MUTED, flexWrap: 'wrap', gap: 6 }}>
          <div>Brand Signal · competitive marketing intelligence</div>
          <div>All figures are computed from tracked data; channels with no captured content show "—" rather than an estimate.</div>
        </div>
      </main>
    </div>
  )
}
