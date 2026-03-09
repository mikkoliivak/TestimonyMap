import { useState } from 'react'

export default function AddTestimony({ centers, onSuccess }) {
  const [facility, setFacility] = useState('')
  const [statement, setStatement] = useState('')
  const [date, setDate] = useState('')
  const [sourceDetails, setSourceDetails] = useState('')
  const [source, setSource] = useState('')
  const [message, setMessage] = useState({ text: '', type: '' })
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setMessage({ text: '', type: '' })
    if (!facility?.trim() || !statement?.trim()) {
      setMessage({ text: 'Please select a facility and enter a testimony.', type: 'error' })
      return
    }
    setSubmitting(true)
    try {
      const res = await fetch('/api/testimonies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          facility: facility.trim(),
          statement: statement.trim(),
          date: date.trim() || 'Unknown',
          'source-details': sourceDetails.trim() || 'Community submission',
          source: source.trim() || '',
        }),
      })
      const data = await res.json()
      if (res.ok && data.ok) {
        setMessage({ text: 'Thank you. Your testimony has been added.', type: 'success' })
        setFacility('')
        setStatement('')
        setDate('')
        setSourceDetails('')
        setSource('')
        onSuccess?.()
      } else {
        setMessage({
          text: data.error || 'Something went wrong. Please try again.',
          type: 'error',
        })
      }
    } catch {
      setMessage({ text: 'Network error. Please try again.', type: 'error' })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section>
      <div className="form-container">
        <h2 className="form-title">Submit a testimony</h2>
        <p className="form-intro">
          Have a quote, article, or firsthand account about a data center or crypto mining facility
          in NY? Add it to the bank.
        </p>
        <form className="add-form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="add-facility">
              Facility / location <span className="required">*</span>
            </label>
            <select
              id="add-facility"
              name="facility"
              required
              value={facility}
              onChange={(e) => setFacility(e.target.value)}
            >
              <option value="">Select a facility…</option>
              {centers.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="add-statement">
              Testimony or quote <span className="required">*</span>
            </label>
            <textarea
              id="add-statement"
              name="statement"
              rows={5}
              required
              placeholder="Paste or type the statement, quote, or summary…"
              value={statement}
              onChange={(e) => setStatement(e.target.value)}
            />
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="add-date">Date (optional)</label>
              <input
                type="text"
                id="add-date"
                name="date"
                placeholder="e.g. 1-15-2024 or Unknown"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="add-source-details">Source name (optional)</label>
              <input
                type="text"
                id="add-source-details"
                name="source-details"
                placeholder="e.g. Ithaca.com, Resident"
                value={sourceDetails}
                onChange={(e) => setSourceDetails(e.target.value)}
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="add-source">Source URL (optional)</label>
            <input
              type="url"
              id="add-source"
              name="source"
              placeholder="https://…"
              value={source}
              onChange={(e) => setSource(e.target.value)}
            />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit testimony'}
            </button>
            {message.text && (
              <p className={`form-message ${message.type}`} aria-live="polite">
                {message.text}
              </p>
            )}
          </div>
        </form>
      </div>
    </section>
  )
}
