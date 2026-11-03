<script setup>
import { useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { homePath } from '../constants/index.js'
const route = useRoute(), auth = useAuthStore()
</script>
<template><div class="error-page"><el-result :icon="route.meta.status === '403' ? 'warning' : 'info'" :title="`${route.meta.status} · ${route.meta.title}`" :sub-title="route.meta.status === '403' ? '您的角色没有访问该页面的权限。' : '请检查页面地址，或返回工作空间。'"><template #extra><el-button type="primary" @click="$router.replace(auth.isAuthenticated ? homePath(auth.role) : '/login')">{{ auth.isAuthenticated ? '返回工作空间' : '前往登录' }}</el-button></template></el-result></div></template>
