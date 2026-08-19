import { ref } from 'vue'

const STORAGE_KEY = 'dc_theme'

function applyTheme(dark) {
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
}

const isDark = ref(localStorage.getItem(STORAGE_KEY) === 'dark')
applyTheme(isDark.value)

export function useTheme() {
  function toggleTheme() {
    isDark.value = !isDark.value
    localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
    applyTheme(isDark.value)
  }

  return { isDark, toggleTheme }
}
