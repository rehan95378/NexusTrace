export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  // Don't set Content-Type for FormData — browser adds boundary
  const headers = {}
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const res = await fetch(`${API_URL}${path}`, {
    headers,
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      // ignore — no JSON body
    }
    throw new Error(detail)
  }
  return res.json()
}

export const api = {
  health: () => request('/health'),

  // Cases
  listCases: () => request('/cases'),
  createCase: (name) => request('/cases', { method: 'POST', body: JSON.stringify({ name }) }),
  renameCase: (caseId, name) =>
    request(`/cases/${caseId}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
  deleteCase: (caseId) => request(`/cases/${caseId}`, { method: 'DELETE' }),

  // Everything below is scoped to one case
  // File-based ingestion (single or multiple files)
  ingest: (caseId, files, append_mode) => {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    formData.append('append_mode', append_mode)
    return request(`/cases/${caseId}/ingest/files`, {
      method: 'POST',
      body: formData,
      // Let browser set Content-Type with boundary
    })
  },
  clearCase: (caseId) => request(`/cases/${caseId}/clear`, { method: 'POST' }),
  entities: (caseId) => request(`/cases/${caseId}/entities`),
  allEntities: () => request('/entities/all'),
  relationshipTypeSuggestions: () => request('/relationship-type-suggestions'),
  graph: (caseId) => request(`/cases/${caseId}/graph`),
  allGraph: () => request('/graph/all'),
  keyPlayers: (caseId) => request(`/cases/${caseId}/analysis/key-players`),
  keyPlayersAll: () => request('/analysis/key-players/all'),
  anomalies: (caseId) => request(`/cases/${caseId}/analysis/anomalies`),
  anomaliesAll: () => request('/analysis/anomalies/all'),
  audit: (caseId) => request(`/cases/${caseId}/audit`),
  auditAll: () => request('/audit/all'),

  // Node click popup: read-only entity detail
  entityDetail: (caseId, type, id) =>
    request(`/cases/${caseId}/entities/${type}/${encodeURIComponent(id)}`),

  // "Edit graph" panel: manual entity + relationship CRUD
  addEntity: (caseId, type, value) =>
    request(`/cases/${caseId}/entities/manual`, {
      method: 'POST',
      body: JSON.stringify({ type, value }),
    }),
  renameEntity: (caseId, type, id, value) =>
    request(`/cases/${caseId}/entities/${type}/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ value }),
    }),
  deleteEntity: (caseId, type, id) =>
    request(`/cases/${caseId}/entities/${type}/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  mergeEntity: (caseId, type, id, mergeWith) =>
    request(`/cases/${caseId}/entities/${type}/${encodeURIComponent(id)}/merge`, {
      method: 'POST',
      body: JSON.stringify({ merge_with: mergeWith }),
    }),
  changeEntityType: (caseId, type, id, newType) =>
    request(`/cases/${caseId}/entities/${type}/${encodeURIComponent(id)}/type`, {
      method: 'PATCH',
      body: JSON.stringify({ new_type: newType }),
    }),
  addRelationship: (caseId, payload) =>
    request(`/cases/${caseId}/relationships`, { method: 'POST', body: JSON.stringify(payload) }),
  renameRelationship: (caseId, payload) =>
    request(`/cases/${caseId}/relationships`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteRelationship: (caseId, payload) =>
    request(`/cases/${caseId}/relationships`, { method: 'DELETE', body: JSON.stringify(payload) }),
}
