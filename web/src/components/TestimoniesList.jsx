import { useMemo, useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { useCentersFull } from '../hooks/useCenters'

function escapeHtml(s) {
  if (s == null) return ''
  const div = document.createElement('div')
  div.textContent = s
  return div.innerHTML
}

function getFilteredTestimonies(centers, query, facilityFilter) {
  const q = (query || '').trim().toLowerCase()
  const list = []
  centers.forEach((c) => {
    if (facilityFilter && c.name !== facilityFilter) return
    ;(c.testimonies || []).forEach((t) => {
      const text = (t.testimonies || t.statement || '').toLowerCase()
      const sourceDetails = (t['source-details'] || '').toLowerCase()
      const sourceUrl = (t.source || '').toLowerCase()
      if (q && !text.includes(q) && !sourceDetails.includes(q) && !sourceUrl.includes(q)) return
      list.push({
        facility: c.name,
        county: c.county,
        submitted: t.submitted,
        testimonies: t.testimonies || t.statement || '',
        date: t.date,
        source: t.source,
        'source-details': t['source-details'],
        article_title: t.article_title,
      })
    })
  })
  return list
}

function TestimonyCard({ t }) {
  const sourceHtml = t['source-details']
    ? t.source
      ? `<a href="${t.source.replace(/"/g, '&quot;')}" target="_blank" rel="noopener">${escapeHtml(t['source-details'])}</a>`
      : escapeHtml(t['source-details'])
    : ''
  const statements = (t.testimonies || '').split('&&').map((s) => s.trim()).filter(Boolean)
  return (
    <article className={`testimony-card ${t.submitted ? 'submitted' : ''}`}>
      {t.article_title && <p className="testimony-article-title">{t.article_title}</p>}
      {statements.map((s, i) => (
        <p key={i} className="testimony-statement">{s}</p>
      ))}
      <div className="testimony-meta">
        <span>
          <strong>{t.facility}</strong>
          {t.county ? ` · ${t.county}` : ''}
        </span>
        <span>{t.date || ''}</span>
        {sourceHtml && (
          <span className="testimony-source" dangerouslySetInnerHTML={{ __html: sourceHtml }} />
        )}
        {t.submitted && <span>Community submission</span>}
      </div>
    </article>
  )
}

export default function TestimoniesList() {
  const location = useLocation()
  const initialFacility = location.state?.facilityFilter || ''
  const [query, setQuery] = useState('')
  const [facilityFilter, setFacilityFilter] = useState(initialFacility)
  const { centers, loading, error } = useCentersFull()

  useEffect(() => {
    if (initialFacility) setFacilityFilter(initialFacility)
  }, [initialFacility])

  const filtered = useMemo(
    () => getFilteredTestimonies(centers, query, facilityFilter),
    [centers, query, facilityFilter]
  )

  if (loading) {
    return <p style={{ color: 'var(--color-text-muted)' }}>Loading testimonies…</p>
  }
  if (error) {
    return <p style={{ color: 'var(--color-text-muted)' }}>Could not load testimonies.</p>
  }
  const countText =
    filtered.length === 0
      ? 'No testimonies match your filters.'
      : `${filtered.length} testimon${filtered.length === 1 ? 'y' : 'ies'}`

  return (
    <section>
      <div className="toolbar">
        <div className="search-wrap">
          <label htmlFor="search-input" className="sr-only">
            Search testimonies
          </label>
          <input
            type="search"
            id="search-input"
            placeholder="Search by keyword (e.g. noise, decibel, residents)…"
            className="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div className="filter-wrap">
          <label htmlFor="filter-facility">Facility</label>
          <select
            id="filter-facility"
            className="filter-select"
            value={facilityFilter}
            onChange={(e) => setFacilityFilter(e.target.value)}
          >
            <option value="">All facilities</option>
            {centers.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="result-count">{countText}</p>
      <div className="testimonies-list">
        {filtered.map((t, i) => (
          <TestimonyCard key={`${t.facility}-${t.testimonies?.slice(0, 30)}-${i}`} t={t} />
        ))}
      </div>
    </section>
  )
}
