import assert from 'node:assert/strict'
import test from 'node:test'

import {
  DEFAULT_REMINDER_INTERVAL_MS,
  OCR_REMINDER_INTERVAL_MS,
  buildManualAlertSpeech,
  compareManualAlerts,
  manualAlertReminderInterval,
} from './manualAlertSpeech.js'

const review = (id, occurredAt = '2026-08-06T10:00:00') => ({
  id,
  entity_type: 'buyer_review',
  expected_buyer: `客户${id}`,
  observed_buyer: `识别${id}`,
  ocr_confidence: 87.26,
  occurred_at: occurredAt,
})

test('OCR 人工审核比普通系统告警拥有更高优先级', () => {
  const items = [
    { id: 'system-1', entity_type: 'system', occurred_at: '2026-08-06T09:00:00' },
    review('review-2', '2026-08-06T11:00:00'),
    review('review-1', '2026-08-06T10:00:00'),
  ].sort(compareManualAlerts)

  assert.deepEqual(items.map(item => item.id), ['review-1', 'review-2', 'system-1'])
})

test('OCR 播报只说明人工判断和待处理数量，不朗读识别详情', () => {
  const result = buildManualAlertSpeech([review('一'), review('二')])

  assert.equal(result.kind, 'buyer_review')
  assert.equal(result.item.id, '一')
  assert.equal(result.text, 'OCR人工审核提醒。当前有2条请求需要人工判断，请尽快处理。')
  assert.doesNotMatch(result.text, /客户|识别结果|置信度|87/)
})

test('多条 OCR 请求会按播报序号循环轮换', () => {
  const items = [review('一'), review('二')]

  assert.equal(buildManualAlertSpeech(items, 1).item.id, '二')
  assert.equal(buildManualAlertSpeech(items, 2).item.id, '一')
})

test('单条 OCR 请求同样不朗读客户或识别信息', () => {
  const result = buildManualAlertSpeech([{
    id: 'review-empty',
    entity_type: 'buyer_review',
    expected_buyer: '홍길동',
    observed_buyer: '',
    ocr_confidence: -1,
  }])

  assert.equal(result.text, 'OCR人工审核提醒。有1条请求需要人工判断，请尽快处理。')
  assert.doesNotMatch(result.text, /홍길동|未识别|置信度/)
})

test('存在 OCR 请求时使用更高的重复提醒频率', () => {
  assert.equal(manualAlertReminderInterval([review('一')]), OCR_REMINDER_INTERVAL_MS)
  assert.equal(
    manualAlertReminderInterval([{ entity_type: 'system' }]),
    DEFAULT_REMINDER_INTERVAL_MS,
  )
  assert.equal(OCR_REMINDER_INTERVAL_MS, 3000)
})
