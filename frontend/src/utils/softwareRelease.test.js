import assert from 'node:assert/strict'
import test from 'node:test'

import {
  extractPackageVersion,
  nextPatchVersion,
  packageFamily,
  suggestReleaseMetadata,
} from './softwareRelease.js'

test('extracts an embedded version without treating platform suffixes as part of it', () => {
  assert.equal(extractPackageVersion('auto-game-executor-v2.3.4-windows-x64.zip'), '2.3.4')
  assert.equal(packageFamily('auto-game-executor-v2.3.4-windows-x64.zip'),
    'auto game executor windows x64')
})

test('increments the patch component of the previous version', () => {
  assert.equal(nextPatchVersion('1.4.2'), '1.4.3')
  assert.equal(nextPatchVersion('1.4'), '1.4.1')
  assert.equal(nextPatchVersion(''), '1.0.0')
})

test('matches the same package family and reuses its latest non-empty notes', () => {
  const history = [
    {
      file_name: 'auto-game-executor-windows-x64.zip',
      version: '1.4.2',
      notes: '',
      uploaded_at: '2026-07-29T10:00:00Z',
    },
    {
      file_name: 'auto-game-executor-v1.4.1-windows-x64.zip',
      version: '1.4.1',
      notes: '游戏机安装后直接运行',
      uploaded_at: '2026-07-28T10:00:00Z',
    },
    {
      file_name: 'auto-monitor-windows-x64.zip',
      version: '9.9.9',
      notes: '不能复用其他软件的描述',
      uploaded_at: '2026-07-29T11:00:00Z',
    },
  ]

  assert.deepEqual(
    suggestReleaseMetadata('auto-game-executor-windows-x64.zip', history),
    {
      version: '1.4.3',
      notes: '游戏机安装后直接运行',
      previous: history[0],
      versionFromFileName: false,
    },
  )
})

test('prefers a version embedded in the selected package name', () => {
  const history = [{
    file_name: '总控客户端-v1.9.0.zip',
    version: '1.9.0',
    notes: '覆盖安装即可',
    uploaded_at: '2026-07-28T10:00:00Z',
  }]

  const result = suggestReleaseMetadata('总控客户端-v2.0.0.zip', history)
  assert.equal(result.version, '2.0.0')
  assert.equal(result.notes, '覆盖安装即可')
  assert.equal(result.versionFromFileName, true)
})
