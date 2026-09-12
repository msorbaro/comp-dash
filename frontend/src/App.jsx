import { useEffect, useState } from 'react'
import Header from './components/Header'
import Landscape from './screens/Landscape'
import Brand from './screens/Brand'
import Channel from './screens/Channel'
import Category from './screens/Category'
import Compare from './screens/Compare'
import { api } from './api'
import { CANVAS, MUTED } from './styles'

export default function App() {
  const [meta, setMeta] = useState(null)
  const [screen, setScreen] = useState('landscape')
  const [brand, setBrand] = useState(null)
  const [channelId, setChannelId] = useState(null)
  const [category, setCategory] = useState(null)
  const [compareA, setCompareA] = useState(null)
  const [compareB, setCompareB] = useState(null)
  const [compareTarget, setCompareTarget] = useState(null) // for the Brand page's "compare with" picker

  useEffect(() => {
    api.meta().then((m) => {
      setMeta(m)
      const firstBrand = m.brands[0]?.name
      setBrand(firstBrand)
      setCategory(m.categories[0]?.name)
      setCompareA(firstBrand)
      setCompareB(m.brands[1]?.name)
      setCompareTarget(m.brands[1]?.name)
    })
  }, [])

  if (!meta) return <div style={{ padding: 100, textAlign: 'center', color: MUTED }}>Loading Brand Signal…</div>

  const goto = (nextScreen) => {
    if (nextScreen !== 'channel') setChannelId(null)
    setScreen(nextScreen)
    window.scrollTo(0, 0)
  }
  const openBrand = (name) => { setBrand(name); goto('brand') }
  const openChannel = (id) => { setChannelId(id); setScreen('channel'); window.scrollTo(0, 0) }
  const openCategory = (name) => { setCategory(name); goto('category') }
  const openCompare = () => { setCompareA(brand); setCompareB(compareTarget); goto('compare') }

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
            onOpenCompare={openCompare}
            compareTarget={compareTarget || meta.brands.find((b) => b.name !== brand)?.name}
            onCompareTargetChange={setCompareTarget}
          />
        )}
        {screen === 'channel' && (
          <Channel
            brand={brand} category={meta.brands.find((b) => b.name === brand)?.category}
            channelId={channelId} onBack={() => goto('brand')}
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
            meta={meta} brandA={compareA || brand} brandB={compareB || compareTarget}
            onBrandAChange={setCompareA} onBrandBChange={setCompareB}
          />
        )}
        <div style={{ marginTop: 28, paddingTop: 16, borderTop: '1px solid #E2E8F0', display: 'flex', justifyContent: 'space-between', fontSize: 10, color: MUTED, flexWrap: 'wrap', gap: 6 }}>
          <div>Brand Signal · competitive marketing intelligence</div>
          <div>All figures are computed from tracked data; channels with no captured content show "—" rather than an estimate.</div>
        </div>
      </main>
    </div>
  )
}
