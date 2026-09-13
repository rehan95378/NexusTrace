import { useState, useRef, useEffect, useCallback } from 'react'
import GraphVisualization from '../components/GraphVisualization'
import UploadPanel from '../components/UploadPanel'
import EntityList from '../components/EntityList'
import RelationshipList from '../components/RelationshipList'
import AlertsPanel from '../components/AlertsPanel'
import '../styles/DashboardPage.css'

export default function DashboardPage({ apiBase, token, user, onLogout }) {
  const [activeTab, setActiveTab] = useState('graph') // graph, entities, relationships, alerts
  const [graphData, setGraphData] = useState(null)
  const [entities, setEntities] = useState([])
  const [relationships, setRelationships] = useState([])
  const [alerts, setAlerts] = useState([])
  const [uploadedReports, setUploadedReports] = useState([])
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState({
    entities: 0,
    relationships: 0,
    alerts: 0,
  })

  const authHeaders = { Authorization: `Bearer ${token}` }

  // Fetch graph data
  const loadGraph = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/graph`, { headers: authHeaders })
      if (!res.ok) throw new Error('Failed to load graph')
      const data = await res.json()
      setGraphData(data)
      setEntities(data.nodes || [])
      setRelationships(data.edges || [])
      setStats((s) => ({ ...s, entities: data.nodes?.length || 0, relationships: data.edges?.length || 0 }))
    } catch (err) {
      console.error('Graph load error:', err)
    }
  }, [apiBase, authHeaders])

  // Fetch alerts
  const loadAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/alerts`, { headers: authHeaders })
      if (!res.ok) throw new Error('Failed to load alerts')
      const data = await res.json()
      setAlerts(data.alerts || [])
      setStats((s) => ({ ...s, alerts: data.alerts?.length || 0 }))
    } catch (err) {
      console.error('Alerts load error:', err)
    }
  }, [apiBase, authHeaders])

  // Load on mount
  useEffect(() => {
    loadGraph()
    loadAlerts()
    const interval = setInterval(() => {
      loadGraph()
      loadAlerts()
    }, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [loadGraph, loadAlerts])

  const handleReportUploaded = useCallback(
    (report) => {
      setUploadedReports((prev) => [report, ...prev])
      loadGraph()
      loadAlerts()
    },
    [loadGraph, loadAlerts]
  )

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <h1>NexusTrace</h1>
          <p>Criminal Network Analysis System</p>
        </div>
        <div className="header-right">
          <span className="user-info">{user?.name || user?.email}</span>
          <button className="btn-logout" onClick={onLogout}>
            Log Out
          </button>
        </div>
      </header>

      <div className="dashboard-container">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-section">
            <h3>Dashboard</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-number">{stats.entities}</div>
                <div className="stat-label">Entities</div>
              </div>
              <div className="stat-card">
                <div className="stat-number">{stats.relationships}</div>
                <div className="stat-label">Relationships</div>
              </div>
              <div className="stat-card alert">
                <div className="stat-number">{stats.alerts}</div>
                <div className="stat-label">Anomalies</div>
              </div>
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Navigation</h3>
            <nav className="nav-tabs">
              <button
                className={`nav-tab ${activeTab === 'graph' ? 'active' : ''}`}
                onClick={() => setActiveTab('graph')}
              >
                🔗 Graph
              </button>
              <button
                className={`nav-tab ${activeTab === 'entities' ? 'active' : ''}`}
                onClick={() => setActiveTab('entities')}
              >
                👤 Entities ({entities.length})
              </button>
              <button
                className={`nav-tab ${activeTab === 'relationships' ? 'active' : ''}`}
                onClick={() => setActiveTab('relationships')}
              >
                ↔️ Relationships ({relationships.length})
              </button>
              <button
                className={`nav-tab ${activeTab === 'alerts' ? 'active' : ''}`}
                onClick={() => setActiveTab('alerts')}
              >
                ⚠️ Anomalies ({alerts.length})
              </button>
            </nav>
          </div>

          <div className="sidebar-section">
            <h3>Upload Report</h3>
            <UploadPanel apiBase={apiBase} token={token} onSuccess={handleReportUploaded} />
          </div>

          <div className="sidebar-section recent">
            <h3>Recent Uploads</h3>
            <div className="recent-list">
              {uploadedReports.slice(0, 5).map((report, idx) => (
                <div key={idx} className="recent-item">
                  <span className="time">{new Date(report.timestamp).toLocaleString()}</span>
                  <span className="type">{report.type}</span>
                </div>
              ))}
              {uploadedReports.length === 0 && <p className="muted">No reports yet</p>}
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="main-content">
          {activeTab === 'graph' && (
            <div className="tab-content">
              <h2>Criminal Network Graph</h2>
              <GraphVisualization data={graphData} loading={loading} />
            </div>
          )}

          {activeTab === 'entities' && (
            <div className="tab-content">
              <h2>Extracted Entities</h2>
              <EntityList entities={entities} />
            </div>
          )}

          {activeTab === 'relationships' && (
            <div className="tab-content">
              <h2>Relationships</h2>
              <RelationshipList relationships={relationships} />
            </div>
          )}

          {activeTab === 'alerts' && (
            <div className="tab-content">
              <h2>Anomalies & Alerts</h2>
              <AlertsPanel alerts={alerts} />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
