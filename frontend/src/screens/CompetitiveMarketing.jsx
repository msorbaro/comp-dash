import Landscape from './Landscape'
import Brand from './Brand'
import Channel from './Channel'
import Category from './Category'
import Compare from './Compare'
import { SLATE_200, SLATE_600, DEEP_TEAL, cardBase } from '../styles'

function pillStyle(active) {
  return {
    fontSize: 11.5, fontWeight: active ? 600 : 500, padding: '7px 13px', borderRadius: 20,
    background: active ? DEEP_TEAL : '#FFFFFF', color: active ? '#FFFFFF' : SLATE_600,
    border: `1px solid ${active ? DEEP_TEAL : SLATE_200}`, cursor: 'pointer', fontFamily: 'Poppins, sans-serif',
  }
}

const VIEWS = [
  { id: 'landscape', label: 'Landscape' },
  { id: 'brand', label: 'Brand deep dive' },
  { id: 'category', label: 'Category rollup' },
  { id: 'compare', label: 'Head to head' },
]

// Landscape/Brand/Category/Head-to-head were four separate top-level tabs;
// they share the same `meta` and cross-link into each other (a brand card
// on Landscape opens Brand deep dive, a brand row on Category opens Brand
// deep dive, etc.), so folding them under one tab with a pill switcher
// (matching the Map/Table/Rollup/... pattern on Customer Voice) removes a
// layer of top-nav clutter without changing any of that cross-linking -
// it's the same onOpenBrand/onOpenCategory handlers from App.jsx, just
// also flipping which pill is active.
export default function CompetitiveMarketing({
  meta, view, onViewChange,
  brand, onBrandChange, channelId, channelTypeFilter, onOpenChannel, onCloseChannel,
  category, onCategoryChange, onOpenCategory,
  compareA, compareB, onCompareAChange, onCompareBChange,
}) {
  return (
    <div>
      <div style={{ ...cardBase, marginBottom: 14, padding: '14px 22px', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {VIEWS.map((v) => (
          <button key={v.id} onClick={() => onViewChange(v.id)} style={pillStyle(view === v.id)}>{v.label}</button>
        ))}
      </div>

      {view === 'landscape' && (
        <Landscape meta={meta} onOpenBrand={onBrandChange} onOpenCategory={onOpenCategory} />
      )}
      {view === 'brand' && (
        channelId != null ? (
          <Channel
            brand={brand} category={meta.brands.find((b) => b.name === brand)?.category}
            channelId={channelId} onBack={onCloseChannel}
            initialTypeFilter={channelTypeFilter}
          />
        ) : (
          <Brand
            meta={meta} brand={brand}
            onBrandChange={onBrandChange}
            onOpenChannel={onOpenChannel}
            onOpenCategory={onOpenCategory}
          />
        )
      )}
      {view === 'category' && (
        <Category
          meta={meta} category={category} focusBrand={brand}
          allCategories={meta.categories.map((c) => c.name)}
          onCategoryChange={onCategoryChange}
          onOpenBrand={onBrandChange}
        />
      )}
      {view === 'compare' && (
        <Compare
          meta={meta} brandA={compareA || brand} brandB={compareB || meta.brands.find((b) => b.name !== brand)?.name}
          onBrandAChange={onCompareAChange} onBrandBChange={onCompareBChange}
        />
      )}
    </div>
  )
}
