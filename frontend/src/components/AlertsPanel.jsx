import '../styles/AlertsPanel.css'

export default function AlertsPanel({ alerts }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className="alerts-panel empty">
        <p>✓ No anomalies detected</p>
      </div>
    )
  }

  return (
    <div className="alerts-panel">
      {alerts.map((alert, idx) => (
        <div key={idx} className={`alert-item ${alert.flags?.[0] || 'default'}`}>
          <div className="alert-header">
            <span className="alert-icon">⚠️</span>
            <strong>{alert.label}</strong>
            <span className="alert-type">{alert.type}</span>
          </div>
          <div className="alert-body">
            <p>{alert.reason}</p>
            {alert.flags?.length > 0 && (
              <div className="alert-flags">
                {alert.flags.map((f) => (
                  <span key={f} className={`flag ${f}`}>
                    {f.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
