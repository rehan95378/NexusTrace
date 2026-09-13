import { useEffect, useRef, useState } from 'react'
import '../styles/GraphVisualization.css'

export default function GraphVisualization({ data, loading }) {
  const containerRef = useRef(null)
  const cyRef = useRef(null)
  const [selectedNode, setSelectedNode] = useState(null)

  useEffect(() => {
    if (!containerRef.current) return
    if (!window.cytoscape) {
      console.warn('Cytoscape not available yet')
      return
    }

    // Use provided data or demo data
    const graphData = data && data.nodes && data.nodes.length > 0 ? data : {
      nodes: [
        { id: 'n1', label: 'Suspect 1', type: 'Person', centrality: 0.8, anomaly_flags: ['high_centrality'] },
        { id: 'n2', label: 'Suspect 2', type: 'Person', centrality: 0.6, anomaly_flags: [] },
        { id: 'n3', label: 'Location A', type: 'Location', centrality: 0.4, anomaly_flags: [] },
        { id: 'n4', label: 'Phone Contact', type: 'Phone', centrality: 0.3, anomaly_flags: ['cross_case_identifier'] },
      ],
      edges: [
        { source: 'n1', target: 'n2', type: 'FAMILY', confidence: 0.85, weight: 1 },
        { source: 'n2', target: 'n3', type: 'LOCATION', confidence: 0.7, weight: 1 },
        { source: 'n1', target: 'n4', type: 'CONTACT', confidence: 0.6, weight: 1 },
      ],
    }

    try {
      // Destroy existing instance
      if (cyRef.current) {
        cyRef.current.destroy()
        cyRef.current = null
      }

      // Build elements
      const elements = []

      graphData.nodes.forEach(n => {
        elements.push({
          data: {
            id: n.id,
            label: n.label || n.id,
            type: n.type || 'Unknown',
            centrality: n.centrality || 0,
            flags: n.anomaly_flags || [],
          }
        })
      })

      graphData.edges.forEach(e => {
        elements.push({
          data: {
            id: `${e.source}-${e.target}`,
            source: e.source,
            target: e.target,
            type: e.type || 'UNKNOWN',
            confidence: e.confidence || 0.5,
          }
        })
      })

      // Create Cytoscape instance
      const cy = window.cytoscape({
        container: containerRef.current,
        elements: elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': '#3b82f6',
              'label': 'data(label)',
              'width': '50px',
              'height': '50px',
              'font-size': '12px',
              'font-weight': 'bold',
              'text-valign': 'center',
              'text-halign': 'center',
              'color': '#fff',
              'text-outline-width': '2px',
              'text-outline-color': '#1e40af',
              'border-width': '2px',
              'border-color': '#1e40af',
              'padding': '8px',
              'text-wrap': 'wrap',
              'text-max-width': '60px',
            }
          },
          {
            selector: 'node[type="Person"]',
            style: { 'background-color': '#3b82f6', 'border-color': '#1e40af' }
          },
          {
            selector: 'node[type="Organization"]',
            style: { 'background-color': '#10b981', 'border-color': '#047857' }
          },
          {
            selector: 'node[type="Location"]',
            style: { 'background-color': '#f59e0b', 'border-color': '#d97706' }
          },
          {
            selector: 'node[type="Phone"]',
            style: { 'background-color': '#ef4444', 'border-color': '#dc2626' }
          },
          {
            selector: 'node[type="Vehicle"]',
            style: { 'background-color': '#8b5cf6', 'border-color': '#7c3aed' }
          },
          {
            selector: 'node[flags *= "high_centrality"]',
            style: {
              'background-color': '#dc2626',
              'border-color': '#991b1b',
              'border-width': '4px',
              'box-shadow': '0 0 20px rgba(220, 38, 38, 0.6)'
            }
          },
          {
            selector: 'node[flags *= "cross_case_identifier"]',
            style: {
              'background-color': '#a855f7',
              'border-color': '#7c3aed',
              'border-width': '4px',
              'box-shadow': '0 0 20px rgba(168, 85, 247, 0.6)'
            }
          },
          {
            selector: 'node:selected',
            style: {
              'border-width': '5px',
              'border-color': '#fff',
              'box-shadow': '0 0 25px rgba(0, 0, 0, 0.3)'
            }
          },
          {
            selector: 'edge',
            style: {
              'line-color': '#d1d5db',
              'width': '2px',
              'target-arrow-color': '#6b7280',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              'opacity': '0.7',
              'label': 'data(type)',
              'font-size': '10px',
              'text-background-color': '#fff',
              'text-background-opaque': true,
              'text-background-padding': '2px'
            }
          },
          {
            selector: 'edge:selected',
            style: {
              'line-color': '#1e40af',
              'width': '3px',
              'opacity': '1'
            }
          }
        ],
        layout: {
          name: 'cose-bilkent',
          directed: false,
          animate: true,
          animationDuration: 800,
          nodeSpacing: 70,
          padding: 50,
          fit: true,
          quality: 'default',
          randomize: true,
          gravity: -2000,
          gravityRange: 500,
          edges: 'straight'
        }
      })

      // Event listeners
      cy.on('tap', 'node', (evt) => {
        const node = evt.target
        setSelectedNode({
          id: node.id(),
          label: node.data('label'),
          type: node.data('type'),
          centrality: node.data('centrality'),
          flags: node.data('flags')
        })
      })

      cy.on('tap', (evt) => {
        if (evt.target === cy) {
          setSelectedNode(null)
        }
      })

      cyRef.current = cy
    } catch (err) {
      console.error('Graph initialization error:', err)
    }

    return () => {
      if (cyRef.current) {
        try {
          cyRef.current.destroy()
        } catch (e) {
          console.error('Cleanup error:', e)
        }
      }
    }
  }, [data])

  return (
    <div className="graph-container">
      <div className="graph-canvas" ref={containerRef}>
        {loading && <div className="loading">Loading graph...</div>}
      </div>
      {selectedNode && (
        <div className="graph-sidebar">
          <div className="node-detail">
            <h3>{selectedNode.label}</h3>
            <div className="detail-row">
              <strong>Type</strong>
              <span className="type-badge" style={{ backgroundColor: getTypeColor(selectedNode.type) }}>
                {selectedNode.type}
              </span>
            </div>
            <div className="detail-row">
              <strong>Centrality Score</strong>
              <span className="score">{selectedNode.centrality.toFixed(3)}</span>
            </div>
            {selectedNode.flags && selectedNode.flags.length > 0 && (
              <div className="detail-row">
                <strong>Anomaly Flags</strong>
                <div className="flags">
                  {selectedNode.flags.map((f, i) => (
                    <span key={i} className={`flag flag-${f}`}>
                      {f === 'high_centrality' ? '🔴' : '🟣'} {f.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
          <button onClick={() => setSelectedNode(null)} className="btn-close">
            Close Details
          </button>
        </div>
      )}
    </div>
  )
}

function getTypeColor(type) {
  const colors = {
    Person: '#3b82f6',
    Organization: '#10b981',
    Location: '#f59e0b',
    Phone: '#ef4444',
    Vehicle: '#8b5cf6',
  }
  return colors[type] || '#6b7280'
}
