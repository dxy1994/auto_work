import request from './request'

// ── 文件上传 ──────────────────────────────────────────────
export const uploadFile = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

// ── 内网软件分发 ──────────────────────────────────────────
export const getSoftwarePackages = () => request.get('/software-packages')
export const uploadSoftwarePackage = (file, metadata = {}, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('version', metadata.version || '')
  formData.append('notes', metadata.notes || '')
  return request.post('/software-packages', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 0,
    onUploadProgress: (event) => {
      if (event.total && onProgress) {
        onProgress(Math.min(99, Math.round((event.loaded * 100) / event.total)))
      }
    },
  })
}
export const deleteSoftwarePackage = (id) => request.delete(`/software-packages/${id}`)
export const softwarePackageDownloadUrl = (id) =>
  `/api/software-packages/${encodeURIComponent(id)}/download`

// ── 系统控制 ──────────────────────────────────────────────
export const getSystemControls = () => request.get('/system-controls')
export const updateSystemControls = (data) => request.put('/system-controls', data)

// ── 网站管理 ──────────────────────────────────────────────
export const getWebsites = (params) => request.get('/platforms', { params })
export const getAllWebsites = () => request.get('/platforms/all')
export const getWebsite = (id) => request.get(`/platforms/${id}`)
export const createWebsite = (data) => request.post('/platforms', data)
export const updateWebsite = (id, data) => request.put(`/platforms/${id}`, data)
export const deleteWebsite = (id) => request.delete(`/platforms/${id}`)
export const getCategories = () => request.get('/platforms/categories')

// ── 账号管理 ──────────────────────────────────────────────
export const getAccounts = (params) => request.get('/platform-accounts', { params })
export const getAccount = (id) => request.get(`/platform-accounts/${id}`)
export const getAccountPassword = (id) => request.get(`/platform-accounts/${id}/password`)
export const createAccount = (data) => request.post('/platform-accounts', data)
export const updateAccount = (id, data) => request.put(`/platform-accounts/${id}`, data)
export const deleteAccount = (id) => request.delete(`/platform-accounts/${id}`)
export const getAllAccounts = () => request.get('/platform-accounts/all')

// ── 平台当前在售商品 ──────────────────────────────────────
export const getPlatformSalesProducts = (params) =>
  request.get('/platform-sales-products', { params })

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
export const addBundleChildren = (bundleId, items) =>
  request.post(`/game-items/bundle/${bundleId}/children`, { items })
export const removeBundleChild = (bundleId, itemId) => request.delete(`/game-items/bundle/${bundleId}/children/${itemId}`)
export const getGameItem = (id) => request.get(`/game-items/${id}`)
export const createGameItem = (data) => request.post('/game-items', data)
export const updateGameItem = (id, data) => request.put(`/game-items/${id}`, data)
export const deleteGameItem = (id) => request.delete(`/game-items/${id}`)

// ── 中控平台：大区物品库存管理 ────────────────────────────
export const getRegionInventories = (params) => request.get('/region-inventories', { params })
export const getAllRegionInventories = (params) => request.get('/region-inventories/all', { params })
export const updateRegionInventory = (id, data) => request.put(`/region-inventories/${id}`, data)
export const updateRegionInventoryBatch = (data) => request.put('/region-inventories/batch/update', data)
export const updateShopPricesBatch = (data) => request.put('/region-inventories/shop-prices/batch', data)
export const stockIn = (data) => request.post('/region-inventories/stock/in', data)
export const stockOut = (data) => request.post('/region-inventories/stock/out', data)
export const getInventoryChangeLogs = (inventoryId) => request.get(`/region-inventories/${inventoryId}/change-logs`)
export const getInventoryShopPrices = (inventoryId) => request.get(`/region-inventories/${inventoryId}/shop-prices`)

// ── 中控平台：机器管理 ────────────────────────────────────
export const getMachines = (params) => request.get('/machines', { params })
export const getAllMachines = () => request.get('/machines/all')
export const getMachine = (id) => request.get(`/machines/${id}`)
export const getMachineSession = (id) => request.get(`/machines/${id}/session`)
export const createMachine = (data) => request.post('/machines', data)
export const updateMachine = (id, data) => request.put(`/machines/${id}`, data)
export const deleteMachine = (id) => request.delete(`/machines/${id}`)

// ── 中控平台：机器关联游戏账号 ────────────────────────────
export const getMachineGames = (machineId) => request.get(`/machines/${machineId}/game-accounts`)
export const addMachineGame = (machineId, data) => request.post(`/machines/${machineId}/game-accounts`, data)
export const updateMachineGame = (mgId, data) => request.put(`/machines/game-accounts/${mgId}`, data)
export const removeMachineGame = (mgId) => request.delete(`/machines/game-accounts/${mgId}`)

// ── 中控平台：机器关联账户 ────────────────────────────────
export const getMachineAccounts = (machineId) => request.get(`/machines/${machineId}/platform-accounts`)
export const addMachineAccount = (machineId, data) => request.post(`/machines/${machineId}/platform-accounts`, data)
export const removeMachineAccount = (maId) => request.delete(`/machines/platform-accounts/${maId}`)

// ── 中控平台：鼠标键盘设备 ──────────────────────────────────
export const getMkDevices = (params) => request.get('/mk-devices', { params })
export const getAllMkDevices = () => request.get('/mk-devices/all')
export const createMkDevice = (data) => request.post('/mk-devices', data)
export const updateMkDevice = (id, data) => request.put(`/mk-devices/${id}`, data)
export const deleteMkDevice = (id) => request.delete(`/mk-devices/${id}`)

// ── Wireless HID 上位机 ────────────────────────────────────────────────────
export const getWirelessHidDevices = () => request.get('/wireless-hid/devices')
export const discoverWirelessHidDevices = (data = {}) =>
  request.post('/wireless-hid/discover', data, { timeout: 10000 })
export const connectWirelessHidDevice = (id) => request.post(`/wireless-hid/${id}/connect`)
export const disconnectWirelessHidDevice = (id) => request.post(`/wireless-hid/${id}/disconnect`)
export const getWirelessHidStatus = (id) => request.get(`/wireless-hid/${id}/status`)
export const sendWirelessHidKeyboard = (id, data) => request.post(`/wireless-hid/${id}/keyboard`, data)
export const sendWirelessHidRelativeMouse = (id, data) => request.post(`/wireless-hid/${id}/mouse/relative`, data)
export const sendWirelessHidAbsoluteMouse = (id, data) => request.post(`/wireless-hid/${id}/mouse/absolute`, data)
export const releaseWirelessHidAll = (id) => request.post(`/wireless-hid/${id}/release-all`)
export const authenticateWirelessHid = (id, pin) =>
  request.post(`/wireless-hid/${id}/management/session`, { pin })
export const getWirelessHidManagementStatus = (id) =>
  request.get(`/wireless-hid/${id}/management/status`)
export const renameWirelessHidDevice = (id, name) =>
  request.post(`/wireless-hid/${id}/management/name`, { name })
export const enterWirelessHidProvisioning = (id) =>
  request.post(`/wireless-hid/${id}/management/provision`)
export const factoryResetWirelessHidDevice = (id, confirmDeviceId) =>
  request.post(`/wireless-hid/${id}/management/factory-reset`, { confirm_device_id: confirmDeviceId })
export const uploadWirelessHidFirmware = (id, file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/wireless-hid/${id}/management/ota`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 210000,
    onUploadProgress: (event) => {
      if (event.total && onProgress) onProgress(Math.round((event.loaded * 100) / event.total))
    },
  })
}
export const provisionWirelessHidAccessPoint = (data) =>
  request.post('/wireless-hid/ap/provision', data, { timeout: 30000 })
export const deleteWirelessHidDevice = (id) => request.delete(`/wireless-hid/${id}`)

// ── 中控平台：视频流设备 ────────────────────────────────────
export const getVsDevices = (params) => request.get('/vs-devices', { params })
export const getAllVsDevices = () => request.get('/vs-devices/all')
export const createVsDevice = (data) => request.post('/vs-devices', data)
export const updateVsDevice = (id, data) => request.put(`/vs-devices/${id}`, data)
export const deleteVsDevice = (id) => request.delete(`/vs-devices/${id}`)

// ── 中控平台：游戏账号 ────────────────────────────────────
export const getGameAccounts = (params) => request.get('/game-accounts', { params })
export const getAllGameAccounts = () => request.get('/game-accounts', { params: { page_size: 1000 } })
export const getGameAccount = (id) => request.get(`/game-accounts/${id}`)
export const createGameAccount = (data) => request.post('/game-accounts', data)
export const updateGameAccount = (id, data) => request.put(`/game-accounts/${id}`, data)
export const deleteGameAccount = (id) => request.delete(`/game-accounts/${id}`)

// ── 中控平台：订单管理 ────────────────────────────────────
export const getOrders = (params) => request.get('/orders', { params })
export const getManualAlerts = () => request.get('/orders/manual-alerts')
export const getSystemAlerts = () => request.get('/system-alerts')
export const dismissSystemAlert = (alertId) => request.post(`/system-alerts/${alertId}/dismiss`)
export const decideBuyerReview = (orderId, data) => request.post(`/orders/${orderId}/buyer-review`, data)
export const getOrder = (id) => request.get(`/orders/${id}`)
export const getOrderLogs = (id) => request.get(`/orders/${id}/logs`)
export const createOrder = (data) => request.post('/orders', data)
export const copyOrder = (id, data) => request.post(`/orders/${id}/copy`, data)
export const updateOrder = (id, data) => request.put(`/orders/${id}`, data)
export const deleteOrder = (id) => request.delete(`/orders/${id}`)
export const reGreeting = (orderId) => request.post(`/orders/${orderId}/re-greeting`)
export const retryOrder = (orderId) => request.post(`/orders/${orderId}/retry`)
export const completeOrder = (orderId) => request.post(`/orders/${orderId}/complete`)
export const cancelOrder = (orderId) => request.post(`/orders/${orderId}/cancel`)
export const sendOrderChat = (orderId, data) => request.post(`/orders/${orderId}/chat`, data)
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
