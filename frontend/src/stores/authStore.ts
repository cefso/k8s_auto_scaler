import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface AuthUser {
  id: number
  username: string
  display_name: string | null
  role: string
  is_active: boolean
}

interface AuthState {
  token: string | null
  user: AuthUser | null
  setAuth: (token: string, user: AuthUser) => void
  clearAuth: () => void
  isAdmin: () => boolean
  canOperate: () => boolean
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      clearAuth: () => set({ token: null, user: null }),
      isAdmin: () => get().user?.role === 'admin',
      canOperate: () => {
        const role = get().user?.role
        return role === 'admin' || role === 'operator'
      },
    }),
    { name: 'k8s-dashboard-auth' }
  )
)
