import { defineStore } from 'pinia'
import { ref } from 'vue'

const THEME_KEY = 'k8s-dashboard-theme'

export type Theme = 'dark' | 'light'

export const useThemeStore = defineStore('theme', () => {
  const saved = localStorage.getItem(THEME_KEY) as Theme | null
  const theme = ref<Theme>(saved === 'light' || saved === 'dark' ? saved : 'dark')

  function setTheme(t: Theme) {
    theme.value = t
    localStorage.setItem(THEME_KEY, t)
    document.documentElement.classList.toggle('theme-light', t === 'light')
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  function initTheme() {
    document.documentElement.classList.toggle('theme-light', theme.value === 'light')
  }

  return { theme, setTheme, toggleTheme, initTheme }
})
