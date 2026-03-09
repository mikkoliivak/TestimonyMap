import { Routes, Route } from 'react-router-dom'
import { useCenters } from './hooks/useCenters'
import Header from './components/Header'
import MapView from './components/MapView'
import TestimoniesList from './components/TestimoniesList'
import AddTestimony from './components/AddTestimony'

function MainContent() {
  const { centers, loading, error, reload } = useCenters()

  if (loading) {
    return (
      <main className="main">
        <p style={{ color: 'var(--color-text-muted)' }}>Loading…</p>
      </main>
    )
  }

  if (error) {
    return (
      <main className="main">
        <p style={{ color: 'var(--color-text-muted)' }}>
          Could not load data. Is the server running?
        </p>
      </main>
    )
  }

  return (
    <main className="main">
      <Routes>
        <Route path="/" element={<MapView centers={centers} />} />
        <Route path="/testimonies" element={<TestimoniesList centers={centers} />} />
        <Route
          path="/add"
          element={<AddTestimony centers={centers} onSuccess={reload} />}
        />
      </Routes>
    </main>
  )
}

export default function App() {
  return (
    <>
      <Header />
      <MainContent />
      <footer className="site-footer">
        <p>
          Research project: mapping resident testimonies about crypto mining and data center
          impacts in New York State.
        </p>
      </footer>
    </>
  )
}
