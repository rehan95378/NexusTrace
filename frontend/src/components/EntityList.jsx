import '../styles/EntityList.css'

const typeIcons = {
  Person: '👤',
  Organization: '🏢',
  Location: '📍',
  Phone: '📱',
  Vehicle: '🚗',
}

export default function EntityList({ entities }) {
  const grouped = entities.reduce((acc, e) => {
    if (!acc[e.type]) acc[e.type] = []
    acc[e.type].push(e)
    return acc
  }, {})

  return (
    <div className="entity-list">
      {Object.entries(grouped).map(([type, items]) => (
        <div key={type} className="entity-group">
          <h3>
            {typeIcons[type] || '•'} {type}s ({items.length})
          </h3>
          <div className="entity-items">
            {items.map((e) => (
              <div key={e.id} className="entity-item">
                <span className="label">{e.label}</span>
                <span className="confidence">
                  {((e.centrality || 0) * 100).toFixed(0)}%
                </span>
                {e.anomaly_flags?.length > 0 && (
                  <span className="flags">
                    {e.anomaly_flags.map((f) => (
                      <span key={f} className="flag">
                        ⚠️ {f}
                      </span>
                    ))}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
