import '../styles/RelationshipList.css'

export default function RelationshipList({ relationships }) {
  const grouped = relationships.reduce((acc, r) => {
    if (!acc[r.type]) acc[r.type] = []
    acc[r.type].push(r)
    return acc
  }, {})

  return (
    <div className="relationship-list">
      {Object.entries(grouped).map(([type, items]) => (
        <div key={type} className="rel-group">
          <h3>{type} ({items.length})</h3>
          <div className="rel-items">
            {items.map((r, idx) => (
              <div
                key={idx}
                className={`rel-item ${r.confidence > 0.7 ? 'high-conf' : 'low-conf'}`}
              >
                <div className="rel-text">
                  <strong>{r.source}</strong>
                  <span className="arrow">→</span>
                  <strong>{r.target}</strong>
                </div>
                <div className="rel-meta">
                  <span className="confidence">
                    {(r.confidence * 100).toFixed(0)}% confidence
                  </span>
                  <span className="weight">Weight: {r.weight}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
