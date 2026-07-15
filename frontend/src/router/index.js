import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/websites',
  },
  {
    path: '/websites',
    name: 'WebsiteList',
    component: () => import('../views/WebsiteList.vue'),
    meta: { title: '网站管理' },
  },
  {
    path: '/accounts',
    name: 'AccountList',
    component: () => import('../views/AccountList.vue'),
    meta: { title: '账号管理' },
  },
  {
    path: '/schedules',
    name: 'ScheduleManagement',
    component: () => import('../views/ScheduleManagement.vue'),
    meta: { title: '子功能配置管理' },
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
    meta: { title: '大区物品库存管理' },
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
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} - 中控平台` : '中控平台'
})

export default router
