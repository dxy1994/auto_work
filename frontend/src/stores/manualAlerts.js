import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  decideBuyerReview as sendBuyerReviewDecision,
  dismissSystemAlert as sendSystemAlertDismiss,
  getManualAlerts,
  getSystemAlerts,
  reportSystemAlertEvent as sendSystemAlertEvent,
} from '../api'
import {
  buildManualAlertSpeech,
  compareManualAlerts,
  manualAlertReminderInterval,
} from '../utils/manualAlertSpeech'

const POLL_INTERVAL_MS = 5000
const VOICE_CONSENT_KEY = 'auto_work_voice_alert_consent_v1'
const VOICE_CONSENT_GRANTED = 'granted'
const SPEECH_START_TIMEOUT_MS = 3000

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
  const reviewDecisionLoading = ref(false)
  const dismissLoadingId = ref(null)

  let pollTimer = null
  let reminderTimer = null
  let requestPending = false
  let lastSignature = ''
  let lastSpokenAt = 0
  let nextBuyerReviewIndex = 0
  let speechStartTimer = null
  let activeUtterance = null
  let started = false
  const presentedAlertIds = new Set()
  const presentingAlertIds = new Set()

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
      + `:${item.last_occurred_at || ''}:${item.occurrence_count || ''}`
    )).join('|')}`
  }

  function nextReminder() {
    return buildManualAlertSpeech(items.value, nextBuyerReviewIndex)
  }

  function cancelSpeech() {
    window.clearTimeout(speechStartTimer)
    speechStartTimer = null
    activeUtterance = null
    if (speechSupported.value) window.speechSynthesis.cancel()
  }

  function reportSystemEvent(item, eventType, details = '') {
    if (item?.entity_type !== 'system' || !item.alert_id) return Promise.resolve(null)
    return sendSystemAlertEvent(item.alert_id, {
      event_type: eventType,
      details,
    }).catch((error) => {
      console.warn(`告警通知事件记录失败: ${eventType}`, error)
      return null
    })
  }

  function reportPresented(item) {
    if (item?.entity_type !== 'system' || !item.alert_id
        || presentedAlertIds.has(item.alert_id)
        || presentingAlertIds.has(item.alert_id)) return
    presentingAlertIds.add(item.alert_id)
    reportSystemEvent(item, 'presented', '告警已进入中控待处理提醒列表')
      .then((response) => {
        if (response) presentedAlertIds.add(item.alert_id)
      })
      .finally(() => presentingAlertIds.delete(item.alert_id))
  }

  function speakText(text, markReminder = false, trackedItem = null) {
    if (!text || !speechSupported.value) return false
    const synth = window.speechSynthesis
    if (synth.speaking || synth.pending) return false

    const utterance = new window.SpeechSynthesisUtterance(text)
    activeUtterance = utterance
    let startedSpeaking = false
    utterance.lang = 'zh-CN'
    utterance.rate = 0.92
    utterance.pitch = 1
    utterance.volume = 1
    const voices = synth.getVoices()
    const chineseVoice = voices.find(voice => /^zh(-|_)/i.test(voice.lang))
    if (chineseVoice) utterance.voice = chineseVoice
    utterance.onstart = () => {
      startedSpeaking = true
      window.clearTimeout(speechStartTimer)
      speechStartTimer = null
      needsInteraction.value = false
      reportSystemEvent(trackedItem, 'voice_started', '中控开始语音播报告警')
    }
    utterance.onend = () => {
      activeUtterance = null
      reportSystemEvent(trackedItem, 'voice_completed', '中控语音播报完成')
    }
    utterance.onerror = (event) => {
      window.clearTimeout(speechStartTimer)
      speechStartTimer = null
      activeUtterance = null
      if (!['canceled', 'interrupted'].includes(event.error)) {
        needsInteraction.value = true
      }
      reportSystemEvent(
        trackedItem,
        'voice_failed',
        `中控语音播报失败: ${event.error || 'unknown'}`,
      )
    }
    synth.speak(utterance)
    // 部分浏览器在未获得用户交互权限时不会触发 error，只会静默丢弃 speak。
    // 超时后将状态显式反馈到页面，并在下一次点击或按键时立即重试。
    window.clearTimeout(speechStartTimer)
    speechStartTimer = window.setTimeout(() => {
      if (!startedSpeaking && !synth.speaking) {
        needsInteraction.value = true
        activeUtterance = null
      }
      speechStartTimer = null
    }, SPEECH_START_TIMEOUT_MS)
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
    const reminder = nextReminder()
    const confirmation = hasAlerts.value
      ? reminder.text
      : '语音提醒已开启。出现需要人工处理的异常时，系统将持续播报。'
    const accepted = speakText(confirmation, hasAlerts.value, reminder.item)
    if (accepted && reminder.kind === 'buyer_review') nextBuyerReviewIndex += 1
    return accepted
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
    const interval = manualAlertReminderInterval(items.value)
    if (!force && now - lastSpokenAt < interval) return false
    const reminder = nextReminder()
    const accepted = speakText(reminder.text, true, reminder.item)
    if (accepted && reminder.kind === 'buyer_review') nextBuyerReviewIndex += 1
    return accepted
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
      const previousItemIds = new Set(items.value.map(item => item.id))
      const nextItems = [
        ...(Array.isArray(orderResponse.items) ? orderResponse.items : []),
        ...(Array.isArray(systemResponse.items) ? systemResponse.items : []),
      ].sort(compareManualAlerts)
      const nextTotal = nextItems.length
      const hasNewBuyerReview = nextItems.some(item => (
        item.entity_type === 'buyer_review' && !previousItemIds.has(item.id)
      ))
      const nextSignature = signatureOf(nextItems, nextTotal)
      const changed = nextSignature !== lastSignature
      items.value = nextItems
      total.value = nextTotal
      nextItems.forEach(reportPresented)
      lastSignature = nextSignature
      fetchError.value = ''
      lastUpdatedAt.value = systemResponse.polled_at || orderResponse.polled_at || new Date().toISOString()
      // OCR 人工审核直接进入通知抽屉。所有机器的 pending 请求都在同一个列表中，
      // 不再用只能展示一条的阻塞弹窗承载，避免后到请求覆盖先到请求。
      if (changed && currentBuyerReview.value && !reviewDecisionLoading.value) {
        drawerVisible.value = true
      }

      if (!nextTotal) {
        if (!voiceConsentRequired.value) cancelSpeech()
        lastSpokenAt = 0
        nextBuyerReviewIndex = 0
        needsInteraction.value = false
      } else if (hasNewBuyerReview) {
        speak(true)
      } else if (changed && !currentBuyerReview.value) {
        speak(true)
      } else {
        // 系统告警发生变化时不抢占或加速 OCR 播报，OCR 仍按自己的高频节奏轮换。
        speak(false)
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
      await refresh()
      return response
    } finally {
      reviewDecisionLoading.value = false
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
