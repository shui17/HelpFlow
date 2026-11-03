<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
const route = useRoute(), router = useRouter(), auth = useAuthStore(), retrying = ref(false)
async function retry() {
  retrying.value = true
  const target = route.query.redirect
  try { await router.replace(typeof target === 'string' && target.startsWith('/') && !target.startsWith('//') && !target.startsWith('/session-unavailable') ? target : '/') }
  finally { retrying.value = false }
}
function login() { auth.logout(); router.replace('/login') }
</script>
<template><div class="error-page"><el-result icon="warning" title="暂时无法恢复登录状态" sub-title="请检查网络或稍后重试，您的登录凭据已保留。"><template #extra><el-button type="primary" :loading="retrying" @click="retry">重新连接</el-button><el-button @click="login">重新登录</el-button></template></el-result></div></template>
