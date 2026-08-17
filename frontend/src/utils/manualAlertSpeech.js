export const OCR_REMINDER_INTERVAL_MS = 3000
export const DEFAULT_REMINDER_INTERVAL_MS = 20000

export function isBuyerReview(item) {
  return item?.entity_type === 'buyer_review'
}

function occurredAt(item) {
  return String(item?.occurred_at || '')
}

/** OCR 人工审核优先展示，同类提醒按发生时间从早到晚处理。 */
export function compareManualAlerts(left, right) {
  const priority = Number(isBuyerReview(right)) - Number(isBuyerReview(left))
  if (priority) return priority
  return occurredAt(left).localeCompare(occurredAt(right))
}

export function manualAlertReminderInterval(items) {
  return items.some(isBuyerReview)
    ? OCR_REMINDER_INTERVAL_MS
    : DEFAULT_REMINDER_INTERVAL_MS
}

function readableText(value, fallback) {
  const text = String(value ?? '').trim()
  return text || fallback
}

/**
 * 生成简短播报内容；OCR 详情只在界面展示，语音不朗读客户或识别信息。
 * 多条 OCR 请求时按 index 轮换，避免第一条请求长期占用播报。
 */
export function buildManualAlertSpeech(items, index = 0) {
  const reviews = items.filter(isBuyerReview)
  if (reviews.length) {
    const normalizedIndex = ((index % reviews.length) + reviews.length) % reviews.length
    const item = reviews[normalizedIndex]
    return {
      item,
      kind: 'buyer_review',
      text: reviews.length > 1
        ? `OCR人工审核提醒。当前有${reviews.length}条请求需要人工判断，请尽快处理。`
        : 'OCR人工审核提醒。有1条请求需要人工判断，请尽快处理。',
    }
  }

  const item = items[0] || null
  return {
    item,
    kind: item ? 'alert' : 'none',
    text: readableText(item?.title, item ? '异常提醒' : ''),
  }
}
