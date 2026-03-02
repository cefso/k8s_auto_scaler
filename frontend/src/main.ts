import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/main.css'

// 尽早应用主题，避免闪烁
const savedTheme = localStorage.getItem('k8s-dashboard-theme')
if (savedTheme === 'light') {
  document.documentElement.classList.add('theme-light')
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
