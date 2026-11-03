<script setup>
defineProps({ loading: Boolean, error: { type: String, default: '' } })
defineEmits(['retry'])
</script>
<template>
  <div v-if="loading" class="panel" role="status" aria-label="正在加载"><el-skeleton :rows="5" animated /></div>
  <div v-else-if="error" class="panel" role="alert"><el-alert :title="error" type="error" :closable="false" show-icon /><el-button class="space-top" @click="$emit('retry')">重新加载</el-button></div>
  <slot v-else />
</template>
