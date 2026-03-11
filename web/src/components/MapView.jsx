import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'

function CenterMarkers({ centers, onViewTestimonies }) {
  if (!centers?.length) return null
  return centers.map((c) => {
    const count = (c.testimonies || []).length
    return (
      <Marker key={c.name} position={[c.lat, c.lng]}>
        <Popup>
          <div className="popup-title">{c.name}</div>
          <div className="popup-meta">
            {c.county || ''} County · {count} testimonies
          </div>
          <a
            href="#"
            className="popup-link"
            onClick={(e) => {
              e.preventDefault()
              onViewTestimonies(c.name)
            }}
          >
            View testimonies →
          </a>
        </Popup>
      </Marker>
    )
  })
}

function MapFitBounds({ centers }) {
  const map = useMap()
  const done = useRef(false)
  useEffect(() => {
    if (!centers?.length || done.current) return
    const bounds = L.latLngBounds(centers.map((c) => [c.lat, c.lng]))
    map.fitBounds(bounds, { padding: [24, 24] })
    done.current = true
  }, [map, centers])
  return null
}

export default function MapView({ centers }) {
  const navigate = useNavigate()

  const handleViewTestimonies = (facility) => {
    navigate('/testimonies', { state: { facilityFilter: facility } })
  }

  if (!centers?.length) {
    return (
      <section className="map-container">
        <div
          className="map"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--color-surface)',
          }}
        >
          <p style={{ color: 'var(--color-text-muted)' }}>No center data to display.</p>
        </div>
        <div className="map-legend">
          <span className="legend-title">Facilities</span>
          <span className="legend-dot" /> Click a marker to see testimony count and link to list.
        </div>
      </section>
    )
  }

  const first = centers[0]
  return (
    <section>
      <div className="map-container">
        <MapContainer
          center={[first.lat, first.lng]}
          zoom={8}
          className="map"
          style={{ height: '70vh', minHeight: 400 }}
        >
          <TileLayer
            url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>'
          />
          <MapFitBounds centers={centers} />
          <CenterMarkers centers={centers} onViewTestimonies={handleViewTestimonies} />
        </MapContainer>
        <div className="map-legend">
          <span className="legend-title">Facilities</span>
          <span className="legend-dot" /> Click a marker to see testimony count and link to list.
        </div>
      </div>
    </section>
  )
}
