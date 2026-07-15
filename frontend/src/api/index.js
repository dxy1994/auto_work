import request from './request'

// ── 文件上传 ──────────────────────────────────────────────
export const uploadFile = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ── 网站管理 ──────────────────────────────────────────────
export const getWebsites = (params) => request.get('/websites', { params })
export const getAllWebsites = () => request.get('/websites/all')
export const getWebsite = (id) => request.get(`/websites/${id}`)
export const createWebsite = (data) => request.post('/websites', data)
export const updateWebsite = (id, data) => request.put(`/websites/${id}`, data)
export const deleteWebsite = (id) => request.delete(`/websites/${id}`)
export const getCategories = () => request.get('/websites/categories')

// ── 账号管理 ──────────────────────────────────────────────
export const getAccounts = (params) => request.get('/accounts', { params })
export const getAccount = (id) => request.get(`/accounts/${id}`)
export const createAccount = (data) => request.post('/accounts', data)
export const updateAccount = (id, data) => request.put(`/accounts/${id}`, data)
export const deleteAccount = (id) => request.delete(`/accounts/${id}`)

// ── 订单查询与提醒 ────────────────────────────────────────
export const orderCheck = (accountId) =>
  request.post('/automation/order-check', null, {
    params: { account_id: accountId },
    timeout: 60000,
  })
export const getOrderCheckStatus = (accountId) =>
  request.get('/automation/order-check/status', {
    params: accountId ? { account_id: accountId } : {},
  })
export const cancelOrderCheck = (accountId) =>
  request.post(`/automation/order-check/${accountId}/cancel`)

// ── 定时执行配置 ──────────────────────────────────────────
export const getAllSchedules = (params) => request.get('/schedules', { params })
export const getSchedule = (accountId) => request.get(`/schedules/${accountId}`)
export const upsertSchedule = (accountId, data) => request.put(`/schedules/${accountId}`, data)
export const copySchedule = (accountId, targetAccountIds) =>
  request.post(`/schedules/${accountId}/copy`, { target_account_ids: targetAccountIds })
export const uploadAlertAudio = (accountId, file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/schedules/${accountId}/audio`, formData)
}

// ── 中控平台：游戏管理 ────────────────────────────────────
export const getGames = (params) => request.get('/games', { params })
export const getAllGames = () => request.get('/games/all')
export const getGame = (id) => request.get(`/games/${id}`)
export const createGame = (data) => request.post('/games', data)
export const updateGame = (id, data) => request.put(`/games/${id}`, data)
export const deleteGame = (id) => request.delete(`/games/${id}`)

// ── 中控平台：游戏大区 ────────────────────────────────────
export const getGameRegions = (params) => request.get('/game-regions', { params })
export const getAllRegions = (gameId) => request.get('/game-regions/all', { params: gameId ? { game_id: gameId } : {} })
export const createRegion = (data) => request.post('/game-regions', data)
export const updateRegion = (id, data) => request.put(`/game-regions/${id}`, data)
export const deleteRegion = (id) => request.delete(`/game-regions/${id}`)

// ── 中控平台：游戏物品 ────────────────────────────────────
export const getGameItems = (params) => request.get('/game-items', { params })
export const getAllItems = (params) => request.get('/game-items/all', { params })
export const getBundles = (gameId) => request.get('/game-items/bundles', { params: gameId ? { game_id: gameId } : {} })
export const getBundleChildren = (bundleId) => request.get(`/game-items/bundle/${bundleId}/children`)
export const getGameItem = (id) => request.get(`/game-items/${id}`)
export const createGameItem = (data) => request.post('/game-items', data)
export const updateGameItem = (id, data) => request.put(`/game-items/${id}`, data)
export const deleteGameItem = (id) => request.delete(`/game-items/${id}`)

// ── 中控平台：大区物品库存管理 ────────────────────────────
export const getRegionInventories = (params) => request.get('/region-inventories', { params })
export const getAllRegionInventories = (params) => request.get('/region-inventories/all', { params })
export const updateRegionInventory = (id, data) => request.put(`/region-inventories/${id}`, data)
export const updateRegionInventoryBatch = (data) => request.put('/region-inventories/batch/update', data)

// ── 中控平台：机器管理 ────────────────────────────────────
export const getMachines = (params) => request.get('/machines', { params })
export const getAllMachines = () => request.get('/machines/all')
export const getMachine = (id) => request.get(`/machines/${id}`)
export const createMachine = (data) => request.post('/machines', data)
export const updateMachine = (id, data) => request.put(`/machines/${id}`, data)
export const deleteMachine = (id) => request.delete(`/machines/${id}`)

// ── 中控平台：机器关联游戏 ────────────────────────────────
export const getMachineGames = (machineId) => request.get(`/machines/${machineId}/games`)
export const addMachineGame = (machineId, data) => request.post(`/machines/${machineId}/games`, data)
export const updateMachineGame = (mgId, data) => request.put(`/machines/games/${mgId}`, data)
export const removeMachineGame = (mgId) => request.delete(`/machines/games/${mgId}`)

// ── 中控平台：游戏账号 ────────────────────────────────────
export const getGameAccounts = (params) => request.get('/game-accounts', { params })
export const getGameAccount = (id) => request.get(`/game-accounts/${id}`)
export const createGameAccount = (data) => request.post('/game-accounts', data)
export const updateGameAccount = (id, data) => request.put(`/game-accounts/${id}`, data)
export const deleteGameAccount = (id) => request.delete(`/game-accounts/${id}`)

// ── 中控平台：订单管理 ────────────────────────────────────
export const getOrders = (params) => request.get('/orders', { params })
export const getOrder = (id) => request.get(`/orders/${id}`)
export const createOrder = (data) => request.post('/orders', data)
export const updateOrder = (id, data) => request.put(`/orders/${id}`, data)
export const deleteOrder = (id) => request.delete(`/orders/${id}`)
export const addOrderDetail = (orderId, data) => request.post(`/orders/${orderId}/details`, data)
export const updateOrderDetail = (detailId, data) => request.put(`/orders/details/${detailId}`, data)
export const deleteOrderDetail = (detailId) => request.delete(`/orders/details/${detailId}`)

// ── 中控平台：话术管理 ────────────────────────────────────
export const getGameScripts = (params) => request.get('/scripts/game', { params })
export const getAllGameScripts = (gameId) => request.get('/scripts/game/all', { params: gameId ? { game_id: gameId } : {} })
export const createGameScript = (data) => request.post('/scripts/game', data)
export const updateGameScript = (id, data) => request.put(`/scripts/game/${id}`, data)
export const deleteGameScript = (id) => request.delete(`/scripts/game/${id}`)

export const getRegionScripts = (params) => request.get('/scripts/region', { params })
export const createRegionScript = (data) => request.post('/scripts/region', data)
export const updateRegionScript = (id, data) => request.put(`/scripts/region/${id}`, data)
export const deleteRegionScript = (id) => request.delete(`/scripts/region/${id}`)
