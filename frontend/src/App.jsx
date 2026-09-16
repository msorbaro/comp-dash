import { useEffect, useState } from 'react'
import Header from './components/Header'
import Landscape from './screens/Landscape'
import Brand from './screens/Brand'
import Channel from './screens/Channel'
import Category from './screens/Category'
import Compare from './screens/Compare'
import Voice from './screens/Voice'
import { Shimmer } from './components/Widgets'
import { api } from './api'
import { CANVAS, MUTED } from './styles'

// Plain URL <-> screen sync via the History API - no router library, matching
// this app's dependency-light convention. 'channel' has no route of its own
// (it's a sub-view of Brand reached by clicking a channel card, not a
// top-level destination) so it maps back to /brand.
const PATH_FOR_SCREEN = { landscape: '/', brand: '/brand', channel: '/brand', category: '/category', compare: '/compare', voice: '/voice' }
const SCREEN_FOR_PATH = { '/': 'landscape', '/brand': 'brand', '/category': 'category', '/compare': 'compare', '/voice': 'voice' }

export default function App() {
  const [meta, setMeta] = useState(null)
  const [screen, setScreen] = useState(() => SCREEN_FOR_PATH[window.location.pathname] || 'landscape')
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
    const onPopState = () => setScreen(SCREEN_FOR_PATH[window.location.pathname] || 'landscape')
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
    if (nextScreen !== 'channel') setChannelId(null)
    // Head to head always opens with the brand currently in focus as Side A,
    // so jumping there from anywhere else is a sensible starting comparison.
    if (nextScreen === 'compare' && screen !== 'compare') setCompareA(brand)
    setScreen(nextScreen)
    const path = PATH_FOR_SCREEN[nextScreen] || '/'
    if (window.location.pathname !== path) window.history.pushState({}, '', path)
    window.scrollTo(0, 0)
  }
  const openBrand = (name) => { setBrand(name); goto('brand') }
  const openChannel = (id, typeFilter = null) => {
    setChannelId(id); setChannelTypeFilter(typeFilter); setScreen('channel')
    if (window.location.pathname !== '/brand') window.history.pushState({}, '', '/brand')
    window.scrollTo(0, 0)
  }
  const openCategory = (name) => { setCategory(name); goto('category') }

  return (
    <div style={{ minHeight: '100vh', background: CANVAS, fontFamily: 'Poppins, system-ui, sans-serif', fontSize: 13, color: '#1A1F26' }}>
      <Header screen={screen} onNav={goto} />
      <main style={{ maxWidth: 1440, margin: '0 auto', padding: '92px 32px 80px' }}>
        {screen === 'landscape' && (
          <Landscape meta={meta} onOpenBrand={openBrand} onOpenCategory={openCategory} />
        )}
        {screen === 'brand' && (
          <Brand
            meta={meta} brand={brand}
            onBrandChange={openBrand}
            onOpenChannel={openChannel}
            onOpenCategory={openCategory}
          />
        )}
        {screen === 'channel' && (
          <Channel
            brand={brand} category={meta.brands.find((b) => b.name === brand)?.category}
            channelId={channelId} onBack={() => goto('brand')}
            initialTypeFilter={channelTypeFilter}
          />
        )}
        {screen === 'category' && (
          <Category
            meta={meta} category={category} focusBrand={brand}
            allCategories={meta.categories.map((c) => c.name)}
            onCategoryChange={setCategory}
            onOpenBrand={openBrand}
          />
        )}
        {screen === 'compare' && (
          <Compare
            meta={meta} brandA={compareA || brand} brandB={compareB || meta.brands.find((b) => b.name !== brand)?.name}
            onBrandAChange={setCompareA} onBrandBChange={setCompareB}
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
