import { useState, useRef, useEffect, useCallback } from 'react'
import './App.css'
import AuthPage from './pages/AuthPage'
import DashboardPage from './pages/DashboardPage'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TOKEN_KEY = 'nexustrace_auth_token'
const USER_KEY = 'nexustrace_user'

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem(USER_KEY)
    return stored ? JSON.parse(stored) : null
  })

  const handleLogin = useCallback((token, userData) => {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(userData))
    setToken(token)
    setUser(userData)
  }, [])

  const handleLogout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    setToken(null)
    setUser(null)
  }, [])

  return (
    <div className="app">
      {!token ? (
        <AuthPage apiBase={API_BASE} onLogin={handleLogin} />
      ) : (
        <DashboardPage
          apiBase={API_BASE}
          token={token}
          user={user}
          onLogout={handleLogout}
        />
      )}
    </div>
  )
}
