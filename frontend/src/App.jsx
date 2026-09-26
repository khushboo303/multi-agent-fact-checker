import { useState } from 'react'
import './App.css'

const API_BASE = 'http://127.0.0.1:8000'

const AGENT_STEPS = [
  { key: 'research', label: 'Research Agent', hint: 'Gathering evidence via web search' },
  { key: 'adversarial', label: 'Adversarial Agent', hint: 'Searching for counter-evidence' },
  { key: 'synthesis', label: 'Synthesis Agent', hint: 'Combining both sides into a brief' },
  { key: 'judge', label: 'Judge Agent', hint: 'Rendering the final verdict' },
]

const IDLE_STEP_STATUS = Object.fromEntries(AGENT_STEPS.map((s) => [s.key, 'pending']))

const VERDICT_STYLES = {
  TRUE: { color: '#22c55e', bg: 'rgba(34, 197, 94, 0.12)' },
  FALSE: { color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)' },
  'PARTIALLY TRUE': { color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)' },
  UNVERIFIABLE: { color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.12)' },
}

function verdictStyle(verdict) {
  return VERDICT_STYLES[verdict?.toUpperCase()] || VERDICT_STYLES.UNVERIFIABLE
}

function Section({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="section">
      <button className="section-header" onClick={() => setOpen((o) => !o)} type="button">
        <span>{title}</span>
        <span className={`chevron ${open ? 'open' : ''}`}>▾</span>
      </button>
      {open && <div className="section-body">{children}</div>}
    </div>
  )
}

function App() {
  const [claim, setClaim] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [stepStatus, setStepStatus] = useState(IDLE_STEP_STATUS)

  const submit = (e) => {
    e.preventDefault()
    const trimmed = claim.trim()
    if (!trimmed || loading) return

    setLoading(true)
    setError(null)
    setResult(null)
    setStepStatus(IDLE_STEP_STATUS)

    // A GET + EventSource stream, one event per agent as it starts/finishes, so the
    // UI reflects the pipeline's real sequential execution instead of a single opaque wait.
    const url = `${API_BASE}/api/check-stream?claim=${encodeURIComponent(trimmed)}`
    const source = new EventSource(url)

    source.addEventListener('step', (evt) => {
      const { agent, state } = JSON.parse(evt.data)
      setStepStatus((prev) => ({ ...prev, [agent]: state }))
    })

    source.addEventListener('final', (evt) => {
      setResult(JSON.parse(evt.data))
      setLoading(false)
      source.close()
    })

    source.addEventListener('error', (evt) => {
      // EventSource fires a plain (data-less) error event on connection failure, and
      // our backend also emits a named "error" SSE event with a JSON message on an
      // agent exception - handle both.
      if (evt.data) {
        try {
          setError(JSON.parse(evt.data).message)
        } catch {
          setError('Something went wrong while fact-checking that claim.')
        }
      } else {
        setError("Can't reach the backend. Is it running at " + API_BASE + '?')
      }
      setLoading(false)
      source.close()
    })
  }

  const style = result ? verdictStyle(result.verdict) : null

  return (
    <div className="page">
      <header className="header">
        <h1>Multi-Agent Fact-Checker</h1>
        <p className="subtitle">
          Research → Adversarial Verification → Synthesis → Judge, running sequentially on
          a local Ollama model.
        </p>
      </header>

      <form className="claim-form" onSubmit={submit}>
        <textarea
          className="claim-input"
          placeholder="Enter a claim to fact-check, e.g. “The Great Wall of China is visible from space with the naked eye.”"
          value={claim}
          onChange={(e) => setClaim(e.target.value)}
          rows={3}
          disabled={loading}
        />
        <button className="submit-btn" type="submit" disabled={loading || !claim.trim()}>
          {loading ? 'Checking…' : 'Fact-check it'}
        </button>
      </form>

      {loading && (
        <div className="progress">
          {AGENT_STEPS.map((step, i) => {
            const status = stepStatus[step.key]
            return (
              <div key={step.key} className={`progress-step status-${status}`}>
                <span className={`dot ${status === 'active' ? 'pulsing' : ''}`}>
                  {status === 'done' ? '✓' : i + 1}
                </span>
                <div>
                  <div className="progress-label">{step.label}</div>
                  <div className="progress-hint">
                    {status === 'done'
                      ? 'Done'
                      : status === 'active'
                      ? step.hint
                      : 'Waiting for previous agent to finish'}
                  </div>
                </div>
              </div>
            )
          })}
          <p className="progress-note">
            Agents run one at a time, in order - each one needs the previous agent's
            output. This can take a few minutes on a local model.
          </p>
        </div>
      )}

      {error && <div className="error-banner">{error}</div>}

      {result && !loading && (
        <div className="result">
          <div className="verdict-card" style={{ borderColor: style.color, background: style.bg }}>
            <div className="verdict-top">
              <span className="verdict-label" style={{ color: style.color }}>
                {result.verdict}
              </span>
              <span className="confidence">{result.confidence}% confidence</span>
            </div>
            <p className="reasoning">{result.reasoning}</p>
          </div>

          <div className="trace">
            {AGENT_STEPS.map((step, i) => (
              <span key={step.key} className="trace-chip">
                {i + 1}. {step.label}
              </span>
            ))}
          </div>

          <Section title="Evidence Synthesis" defaultOpen>
            <p className="pre">{result.synthesis}</p>
          </Section>
          <Section title="Research Findings">
            <p className="pre">{result.research_findings}</p>
          </Section>
          <Section title="Adversarial Findings">
            <p className="pre">{result.adversarial_findings}</p>
          </Section>
        </div>
      )}
    </div>
  )
}

export default App
