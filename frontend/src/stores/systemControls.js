import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getSystemControls, updateSystemControls } from '../api'

export const useSystemControlStore = defineStore('systemControls', () => {
  const loading = ref(false)
  const loaded = ref(false)
  const loadError = ref('')
  const autoTradeEnabled = ref(false)
  const pageGuidesVisible = ref(true)
  const updatedAt = ref(null)

  function applyControls(response) {
    autoTradeEnabled.value = Boolean(response.auto_game_trade_enabled)
    pageGuidesVisible.value = response.page_guides_visible !== false
    updatedAt.value = response.updated_at
    loaded.value = true
    loadError.value = ''
  }

  async function load(force = false) {
    if (loading.value || (loaded.value && !force)) return
    loading.value = true
    loadError.value = ''
    try {
      applyControls(await getSystemControls())
    } catch (error) {
      loadError.value = error.message || '无法连接中控后端'
    } finally {
      loading.value = false
    }
  }

  async function update(changes) {
    const response = await updateSystemControls(changes)
    applyControls(response)
    return response
  }

  return {
    loading,
    loaded,
    loadError,
    autoTradeEnabled,
    pageGuidesVisible,
    updatedAt,
    load,
    update,
  }
})
