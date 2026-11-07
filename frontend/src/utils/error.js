import { ElMessage } from 'element-plus/es/components/message/index.mjs'
import { ElMessageBox } from 'element-plus/es/components/message-box/index.mjs'

export function errorMessage(error) {
  if (error.response?.status === 422) {
    const fields = error.response.data?.data
    if (Array.isArray(fields)) return fields.map((item) => item.message || item.msg).filter(Boolean).join('；') || '输入格式有误，请检查后重试'
    return error.response.data?.message || '输入格式有误，请检查后重试'
  }
  return error.response?.data?.message || (error.response ? '系统暂时不可用' : '无法连接服务器，请检查后端是否启动')
}
export const notifyError = (error) => ElMessage.error(errorMessage(error))
export async function confirmAction(message, options = {}) {
  try {
    await ElMessageBox.confirm(message, '确认操作', { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning', ...options })
    return true
  } catch { return false }
}
