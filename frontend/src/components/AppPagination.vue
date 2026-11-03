<script setup>
defineProps({ page: Number, pageSize: { type: Number, default: 10 }, total: Number })
defineEmits(['change'])
</script>
<template><div class="pagination"><span class="muted">共 {{ total }} 条记录</span><el-pagination :current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" background @current-change="$emit('change', $event)" /></div></template>
