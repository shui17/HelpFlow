<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { roles, homePath } from '../constants/index.js'
import AppIcon from '../components/AppIcon.vue'
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const collapsed = ref(false)
const menus = computed(() => [
  [homePath(auth.role), auth.role === 'agent' ? '工作台' : '概览', 'grid'],
  ...({ user: [['/user/tickets', '我的工单', 'ticket'], ['/user/tickets/create', '创建工单', 'plus']], agent: [['/agent/tickets/unassigned', '待领取工单', 'ticket'], ['/agent/tickets/mine', '我负责的工单', 'check']], admin: [['/admin/tickets', '全部工单', 'ticket'], ['/admin/users', '用户管理', 'users']] }[auth.role] || []),
  ['/profile', '个人中心', 'user'],
])
function logout() { auth.logout(); router.replace('/login') }
</script>
<template>
  <div v-if="auth.isAuthenticated" class="app-shell" :class="{ collapsed }">
    <aside class="sidebar">
      <router-link :to="homePath(auth.role)" class="brand"><span class="brand-mark">H</span><span v-if="!collapsed">HelpFlow<small>客户支持工作空间</small></span></router-link>
      <div v-if="!collapsed" class="nav-label">工作空间</div>
      <nav aria-label="主导航"><router-link v-for="[path, label, icon] in menus" :key="path" :to="path" :title="label" :class="{ active: route.path === path }" :aria-current="route.path === path ? 'page' : undefined"><AppIcon :name="icon" class="nav-icon" /><span v-if="!collapsed">{{ label }}</span></router-link></nav>
      <div class="sidebar-footer"><span v-if="!collapsed">让每个问题，都有回应。</span><el-button text :aria-label="collapsed ? '展开菜单' : '折叠菜单'" @click="collapsed = !collapsed">{{ collapsed ? '›' : '‹' }}</el-button></div>
    </aside>
    <div class="workspace">
      <header class="topbar"><span>工作空间 <span class="muted">/</span> {{ route.meta.title }}</span><div class="user-menu"><span class="avatar">{{ auth.currentUser?.username.slice(0, 1) }}</span><span>{{ auth.currentUser?.username }}</span><el-tag size="small" type="info">{{ roles[auth.role] }}</el-tag><el-button text @click="logout">退出</el-button></div></header>
      <main class="main-content"><router-view :key="route.path" /></main>
      <footer class="workspace-footer">HelpFlow · 连接问题与解决方案</footer>
    </div>
  </div>
</template>
