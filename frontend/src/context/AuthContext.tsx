import { createContext, useContext, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router'

// 1. Definiere Typen
interface AuthContextType {
  user: { username: string } | null
  login: (username: string, password: string) => void
  register: (username: string, password: string) => void
  logout: () => void
}

// 2. Initialer (leerer) Context mit Platzhalterfunktionen
const AuthContext = createContext<AuthContextType>({
  user: null,
  login: () => {},
  register: () => {},
  logout: () => {},
})

// 3. Provider-Komponente
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<{ username: string } | null>(null)
  const navigate = useNavigate()

  const login = (username: string, password: string) => {
    console.log(password);
    setUser({ username })
    navigate('/')
  }

  const register = (username: string, password: string) => {
    console.log(password);
    setUser({ username })
    navigate('/')
  }

  const logout = () => {
    setUser(null)
    navigate('/login')
  }

  return (
    <AuthContext.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// 4. Custom Hook
export const useAuth = () => useContext(AuthContext)
