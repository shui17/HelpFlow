<script setup>
import { useAuthStore } from '../stores/auth.js'
import { roles } from '../constants/index.js'
import { formatDate } from '../utils/datetime.js'
const auth = useAuthStore()
</script>
<template><div class="page-heading"><div><div class="eyebrow">ACCOUNT</div><h1>个人中心</h1><p class="muted">您的账号信息与安全设置。</p></div></div><section class="panel form-panel"><div class="section-heading"><h2>账号信息</h2><el-tag type="success">{{ auth.currentUser.is_active ? '账号已启用' : '账号已禁用' }}</el-tag></div><el-descriptions :column="1" border><el-descriptions-item label="用户编号">{{ auth.currentUser.id }}</el-descriptions-item><el-descriptions-item label="用户名">{{ auth.currentUser.username }}</el-descriptions-item><el-descriptions-item label="邮箱">{{ auth.currentUser.email }}</el-descriptions-item><el-descriptions-item label="注册时间">{{ formatDate(auth.currentUser.created_at) }}</el-descriptions-item><el-descriptions-item label="角色">{{ roles[auth.role] }}</el-descriptions-item></el-descriptions><el-button type="primary" class="space-top" @click="$router.push('/change-password')">修改密码</el-button></section></template>
