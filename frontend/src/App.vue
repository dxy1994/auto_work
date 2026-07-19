<template>
  <el-container class="app-wrapper">
    <!-- 侧边栏 -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon size="24"><Monitor /></el-icon>
        <span>中控平台</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#409eff"
      >
        <el-sub-menu index="platform">
          <template #title>
            <el-icon><Connection /></el-icon>
            <span>平台接入</span>
          </template>
          <el-menu-item index="/platforms">
            <el-icon><Grid /></el-icon>
            <span>交易平台</span>
          </el-menu-item>
          <el-menu-item index="/platform-accounts">
            <el-icon><User /></el-icon>
            <span>平台账号</span>
          </el-menu-item>
          <el-menu-item index="/platform-schedules">
            <el-icon><Clock /></el-icon>
            <span>定时调度</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="game-config">
          <template #title>
            <el-icon><Trophy /></el-icon>
            <span>游戏配置</span>
          </template>
          <el-menu-item index="/games">
            <el-icon><Trophy /></el-icon>
            <span>游戏管理</span>
          </el-menu-item>
          <el-menu-item index="/game-items">
            <el-icon><GoodsFilled /></el-icon>
            <span>游戏物品</span>
          </el-menu-item>
          <el-menu-item index="/region-inventories">
            <el-icon><Box /></el-icon>
            <span>大区库存</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="machine">
          <template #title>
            <el-icon><Monitor /></el-icon>
            <span>机器管理</span>
          </template>
          <el-menu-item index="/machines">
            <el-icon><Monitor /></el-icon>
            <span>机器列表</span>
          </el-menu-item>
          <el-menu-item index="/game-accounts">
            <el-icon><Avatar /></el-icon>
            <span>游戏账号</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="order">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>订单交易</span>
          </template>
          <el-menu-item index="/orders">
            <el-icon><Document /></el-icon>
            <span>订单管理</span>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="device">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>设备管理</span>
          </template>
          <el-menu-item index="/mk-devices">
            <el-icon><Mouse /></el-icon>
            <span>键鼠设备</span>
          </el-menu-item>
          <el-menu-item index="/vs-devices">
            <el-icon><VideoCameraFilled /></el-icon>
            <span>视频流设备</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-main class="main-content">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style>
/* 全局样式 */
*, *::before, *::after { box-sizing: border-box; }
html, body, #app { height: 100%; margin: 0; padding: 0; }

.app-wrapper { height: 100vh; }

.sidebar {
  background-color: #001529;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  border-bottom: 1px solid #ffffff1a;
}
.sidebar-menu { border-right: none; flex: 1; }

.main-content {
  background: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}
</style>
