import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getManualAlerts } from '../api'

const POLL_INTERVAL_MS = 5000
const REMINDER_INTERVAL_MS = 20000

export const useManualAlertStore = defineStore('manual-alerts', () => {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const fetchError = ref('')
  const drawerVisible = ref(false)
  const needsInteraction = ref(false)
  const lastUpdatedAt = ref(null)

  let pollTimer = null
  let reminderTimer = null
  let requestPending = false
  let lastSignature = ''
  let lastSpokenAt = 0
  let started = false

  const speechSupported = computed(() => (
    typeof window !== 'undefined'
    && 'speechSynthesis' in window
    && 'SpeechSynthesisUtterance' in window
  ))
  const hasAlerts = computed(() => total.value > 0)

  function signatureOf(nextItems, nextTotal) {
    return `${nextTotal}|${nextItems.map(item => (
      `${item.id}:${item.delivery_status}:${item.error_code || ''}:${item.occurred_at || ''}`
    )).join('|')}`
  }

  function reminderText() {
    if (!hasAlerts.value) return ''
    const first = items.value[0]
    const orderNo = first?.source_order_no || first?.order_no || first?.entity_id || ''
    const firstDescription = first
      ? `。最早一条是订单${orderNo}，${first.title}，${first.message}`
      : ''
    return `中控平台有${total.value}条异常需要人工处理${firstDescription}。请尽快打开待处理列表。`
  }

  function cancelSpeech() {
    if (speechSupported.value) window.speechSynthesis.cancel()
  }

  function speak(force = false) {
    if (!hasAlerts.value || !speechSupported.value) return false
    const now = Date.now()
    if (!force && now - lastSpokenAt < REMINDER_INTERVAL_MS) return false
    const synth = window.speechSynthesis
    if (synth.speaking || synth.pending) return false

    const utterance = new window.SpeechSynthesisUtterance(reminderText())
    utterance.lang = 'zh-CN'
    utterance.rate = 0.92
    utterance.pitch = 1
    utterance.volume = 1
    const voices = synth.getVoices()
    const chineseVoice = voices.find(voice => /^zh(-|_)/i.test(voice.lang))
    if (chineseVoice) utterance.voice = chineseVoice
    utterance.onstart = () => { needsInteraction.value = false }
    utterance.onerror = (event) => {
      if (!['canceled', 'interrupted'].includes(event.error)) {
        needsInteraction.value = true
      }
    }
    synth.speak(utterance)
    lastSpokenAt = now
    return true
  }

  async function refresh() {
    if (requestPending) return
    requestPending = true
    loading.value = true
    try {
      const response = await getManualAlerts()
      const nextItems = Array.isArray(response.items) ? response.items : []
      const nextTotal = Number(response.total || 0)
      const nextSignature = signatureOf(nextItems, nextTotal)
      const changed = nextSignature !== lastSignature
      items.value = nextItems
      total.value = nextTotal
      lastSignature = nextSignature
      fetchError.value = ''
      lastUpdatedAt.value = response.polled_at || new Date().toISOString()

      if (!nextTotal) {
        cancelSpeech()
        lastSpokenAt = 0
        needsInteraction.value = false
      } else if (changed) {
        speak(true)
      }
    } catch (error) {
      // 轮询失败不清空上次异常，防止后端短暂断线导致语音被静默。
      fetchError.value = error.message || '待处理消息刷新失败'
    } finally {
      requestPending = false
      loading.value = false
    }
  }

  function handleUserInteraction() {
    if (hasAlerts.value && needsInteraction.value) speak(true)
  }

  function start() {
    if (started) return
    started = true
    refresh()
    pollTimer = window.setInterval(refresh, POLL_INTERVAL_MS)
    reminderTimer = window.setInterval(() => speak(false), 1000)
    window.addEventListener('pointerdown', handleUserInteraction)
    window.addEventListener('keydown', handleUserInteraction)
  }

  function stop() {
    if (!started) return
    started = false
    window.clearInterval(pollTimer)
    window.clearInterval(reminderTimer)
    window.removeEventListener('pointerdown', handleUserInteraction)
    window.removeEventListener('keydown', handleUserInteraction)
    cancelSpeech()
  }

  return {
    items,
    total,
    loading,
    fetchError,
    drawerVisible,
    needsInteraction,
    lastUpdatedAt,
    speechSupported,
    hasAlerts,
    refresh,
    speak,
    start,
    stop,
  }
})
