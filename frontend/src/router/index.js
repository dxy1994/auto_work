import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/platforms',
  },
  {
    path: '/platforms',
    name: 'PlatformList',
    component: () => import('../views/WebsiteList.vue'),
    meta: { title: '交易平台' },
  },
  {
    path: '/platform-accounts',
    name: 'PlatformAccountList',
    component: () => import('../views/AccountList.vue'),
    meta: { title: '平台账号' },
  },
  // ── 中控平台 ──
  {
    path: '/games',
    name: 'GameList',
    component: () => import('../views/GameList.vue'),
    meta: { title: '游戏管理' },
  },
  {
    path: '/game-items',
    name: 'GameItemList',
    component: () => import('../views/GameItemList.vue'),
    meta: { title: '游戏物品管理' },
  },
  {
    path: '/region-inventories',
    name: 'RegionInventoryList',
    component: () => import('../views/RegionInventoryList.vue'),
    meta: { title: '大区库存' },
  },
  {
    path: '/machines',
    name: 'MachineList',
    component: () => import('../views/MachineList.vue'),
    meta: { title: '机器管理' },
  },
  {
    path: '/game-accounts',
    name: 'GameAccountList',
    component: () => import('../views/GameAccountList.vue'),
    meta: { title: '游戏账号管理' },
  },
  {
    path: '/orders',
    name: 'OrderList',
    component: () => import('../views/OrderList.vue'),
    meta: { title: '订单管理' },
  },
  {
    path: '/mk-devices',
    name: 'MouseKeyboardDeviceList',
    component: () => import('../views/MouseKeyboardDeviceList.vue'),
    meta: { title: 'Wireless HID 上位机' },
  },
  {
    path: '/vs-devices',
    name: 'VideoStreamDeviceList',
    component: () => import('../views/VideoStreamDeviceList.vue'),
    meta: { title: '视频流设备管理' },
  },
  {
    path: '/software-distribution',
    name: 'SoftwareDistribution',
    component: () => import('../views/SoftwareDistribution.vue'),
    meta: { title: '内网软件分发' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - 中控平台` : '中控平台'
})

export default router
