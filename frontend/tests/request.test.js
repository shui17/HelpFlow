import { beforeEach, expect, it, vi } from 'vitest'
import request, { onUnauthorized } from '../src/utils/request.js'
import { errorMessage } from '../src/utils/error.js'

vi.mock('element-plus/es/components/message/index.mjs', () => ({ ElMessage: { error: vi.fn() } }))
vi.mock('element-plus/es/components/message-box/index.mjs', () => ({ ElMessageBox: { confirm: vi.fn() } }))
const storage = new Map()
vi.stubGlobal('localStorage', { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) })
beforeEach(() => { storage.clear() })

it('发送 Bearer Token 并解包响应数据', async () => {
  localStorage.setItem('helpflow.access_token', 'test-token')
  const adapter = vi.fn(async (config) => ({ config, status: 200, data: { code: 0, message: 'success', data: { id: 12 } } }))
  expect(await request.get('/tickets/12', { adapter })).toEqual({ id: 12 })
  expect(adapter.mock.calls[0][0].headers.Authorization).toBe('Bearer test-token')
})
it('当前会话 401 会清除 token，且保留错误供页面展示', async () => {
  localStorage.setItem('helpflow.access_token', 'expired-token')
  const handler = vi.fn(); onUnauthorized(handler)
  const adapter = async (config) => { throw { config, response: { status: 401, data: { message: '登录已过期' } } } }
  await expect(request.get('/auth/me', { adapter })).rejects.toMatchObject({ response: { status: 401 } })
  expect(handler).toHaveBeenCalledOnce()
  expect(localStorage.getItem('helpflow.access_token')).toBeNull()
})
it('旧请求的 401 不会清除刚建立的新会话', async () => {
  localStorage.setItem('helpflow.access_token', 'old-token')
  const handler = vi.fn(); onUnauthorized(handler)
  const adapter = async (config) => {
    localStorage.setItem('helpflow.access_token', 'new-token')
    throw { config, response: { status: 401 } }
  }
  await expect(request.get('/tickets', { adapter })).rejects.toBeDefined()
  expect(handler).not.toHaveBeenCalled()
  expect(localStorage.getItem('helpflow.access_token')).toBe('new-token')
})
it('使用后端校验与冲突信息，连接失败显示可理解的提示', () => {
  expect(errorMessage({ response: { status: 422, data: { data: [{ message: '两次密码不一致' }] } } })).toBe('两次密码不一致')
  expect(errorMessage({ response: { status: 409, data: { message: '工单已被领取' } } })).toBe('工单已被领取')
  expect(errorMessage(new Error('Network Error'))).toContain('无法连接服务器')
})
