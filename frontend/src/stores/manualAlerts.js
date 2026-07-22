import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  decideBuyerReview as sendBuyerReviewDecision,
  dismissSystemAlert as sendSystemAlertDismiss,
  getManualAlerts,
  getSystemAlerts,
} from '../api'

const POLL_INTERVAL_MS = 5000
const REMINDER_INTERVAL_MS = 20000
const VOICE_CONSENT_KEY = 'auto_work_voice_alert_consent_v1'
const VOICE_CONSENT_GRANTED = 'granted'

export const useManualAlertStore = defineStore('manual-alerts', () => {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const fetchError = ref('')
  const drawerVisible = ref(false)
  const needsInteraction = ref(false)
  const voiceConsentRequired = ref(false)
  const voiceConsentGranted = ref(false)
  const lastUpdatedAt = ref(null)
  const reviewDialogVisible = ref(false)
  const reviewDecisionLoading = ref(false)
  const dismissLoadingId = ref(null)

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
  const currentBuyerReview = computed(() => (
    items.value.find(item => item.entity_type === 'buyer_review') || null
  ))

  function signatureOf(nextItems, nextTotal) {
    return `${nextTotal}|${nextItems.map(item => (
      `${item.id}:${item.delivery_status}:${item.error_code || ''}:${item.occurred_at || ''}`
    )).join('|')}`
  }

  function reminderText() {
    if (!hasAlerts.value) return ''
    const first = items.value[0]
    const orderNo = first?.source_order_no || first?.order_no || first?.entity_id || ''
    const firstDescription = first?.entity_type === 'system'
      ? `。最早一条是${first.title}，${first.message}`
      : first ? `。最早一条是订单${orderNo}，${first.title}，${first.message}` : ''
    return `中控平台有${total.value}条异常需要人工处理${firstDescription}。请尽快打开待处理列表。`
  }

  function cancelSpeech() {
    if (speechSupported.value) window.speechSynthesis.cancel()
  }

  function speakText(text, markReminder = false) {
    if (!text || !speechSupported.value) return false
    const synth = window.speechSynthesis
    if (synth.speaking || synth.pending) return false

    const utterance = new window.SpeechSynthesisUtterance(text)
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
    if (markReminder) lastSpokenAt = Date.now()
    return true
  }

  function promptVoiceConsent() {
    voiceConsentRequired.value = true
    return speakText('中控平台请求开启语音提醒。请点击同意并开启语音提醒。')
  }

  function grantVoiceConsent() {
    try {
      window.localStorage.setItem(VOICE_CONSENT_KEY, VOICE_CONSENT_GRANTED)
    } catch (_error) {
      // 隐私模式禁用 localStorage 时，本次会话仍可正常开启。
    }
    voiceConsentGranted.value = true
    voiceConsentRequired.value = false
    needsInteraction.value = false
    cancelSpeech()
    const confirmation = hasAlerts.value
      ? `语音提醒已开启。${reminderText()}`
      : '语音提醒已开启。出现需要人工处理的异常时，系统将持续播报。'
    return speakText(confirmation, hasAlerts.value)
  }

  function loadVoiceConsent() {
    let granted = false
    try {
      granted = window.localStorage.getItem(VOICE_CONSENT_KEY) === VOICE_CONSENT_GRANTED
    } catch (_error) {
      granted = false
    }
    voiceConsentGranted.value = granted
    voiceConsentRequired.value = !granted
    if (!granted) window.setTimeout(promptVoiceConsent, 0)
  }

  function speak(force = false) {
    if (!voiceConsentGranted.value) {
      promptVoiceConsent()
      return false
    }
    if (!hasAlerts.value || !speechSupported.value) return false
    const now = Date.now()
    if (!force && now - lastSpokenAt < REMINDER_INTERVAL_MS) return false
    return speakText(reminderText(), true)
  }

  async function refresh() {
    if (requestPending) return
    requestPending = true
    loading.value = true
    try {
      const [orderResponse, systemResponse] = await Promise.all([
        getManualAlerts(),
        getSystemAlerts(),
      ])
      const nextItems = [
        ...(Array.isArray(orderResponse.items) ? orderResponse.items : []),
        ...(Array.isArray(systemResponse.items) ? systemResponse.items : []),
      ].sort((a, b) => String(a.occurred_at || '').localeCompare(String(b.occurred_at || '')))
      const nextTotal = nextItems.length
      const nextSignature = signatureOf(nextItems, nextTotal)
      const changed = nextSignature !== lastSignature
      items.value = nextItems
      total.value = nextTotal
      lastSignature = nextSignature
      fetchError.value = ''
      lastUpdatedAt.value = systemResponse.polled_at || orderResponse.polled_at || new Date().toISOString()
      if (currentBuyerReview.value && !reviewDecisionLoading.value) {
        reviewDialogVisible.value = true
      } else if (!currentBuyerReview.value) {
        reviewDialogVisible.value = false
      }

      if (!nextTotal) {
        if (!voiceConsentRequired.value) cancelSpeech()
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

  async function decideBuyerReview(item, approved) {
    if (!item || reviewDecisionLoading.value) return null
    reviewDecisionLoading.value = true
    try {
      const response = await sendBuyerReviewDecision(item.entity_id, {
        review_id: item.review_id,
        approved: Boolean(approved),
      })
      reviewDialogVisible.value = false
      await refresh()
      return response
    } finally {
      reviewDecisionLoading.value = false
      if (currentBuyerReview.value) reviewDialogVisible.value = true
    }
  }

  async function dismissSystemAlert(item) {
    if (!item?.alert_id || dismissLoadingId.value) return null
    dismissLoadingId.value = item.id
    try {
      const response = await sendSystemAlertDismiss(item.alert_id)
      await refresh()
      return response
    } finally {
      dismissLoadingId.value = null
    }
  }

  function handleUserInteraction() {
    if (!needsInteraction.value) return
    if (voiceConsentRequired.value) promptVoiceConsent()
    else if (hasAlerts.value) speak(true)
  }

  function start() {
    if (started) return
    started = true
    loadVoiceConsent()
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
    voiceConsentRequired,
    voiceConsentGranted,
    lastUpdatedAt,
    reviewDialogVisible,
    reviewDecisionLoading,
    dismissLoadingId,
    speechSupported,
    hasAlerts,
    currentBuyerReview,
    refresh,
    speak,
    grantVoiceConsent,
    decideBuyerReview,
    dismissSystemAlert,
    start,
    stop,
  }
})
