import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ticketPermissions } from '../src/utils/permissions.js'
import { formatDate } from '../src/utils/datetime.js'
import { createPinia, setActivePinia } from 'pinia'
import { routeAccess } from '../src/router/access.js'
import { createRouter, createMemoryHistory } from 'vue-router'
import { routes } from '../src/router/routes.js'

vi.mock('../src/api/auth.js', () => ({ getCurrentUser: vi.fn(), login: vi.fn(), register: vi.fn(), changePassword: vi.fn() }))
const storage = new Map()
vi.stubGlobal('localStorage', { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) })
const authApi = await import('../src/api/auth.js')
const { useAuthStore } = await import('../src/stores/auth.js')

describe('工单权限与合法流转入口', () => {
  const user = { id: 1, role: 'user' }, agent = { id: 2, role: 'agent' }, admin = { id: 3, role: 'admin' }
  const ticket = { creator_id: 1, assignee_id: null, status: 'open' }
  it('退出或会话过期期间无当前用户时所有操作均关闭', () => {
    expect(Object.values(ticketPermissions(ticket, null)).every((value) => !value)).toBe(true)
  })
  it('用户仅能编辑和撤销自己未分配的待处理工单', () => {
    expect(ticketPermissions(ticket, user).edit).toBe(true)
    expect(ticketPermissions({ ...ticket, assignee_id: 2 }, user).edit).toBe(false)
    expect(ticketPermissions(ticket, { ...user, id: 9 }).edit).toBe(false)
  })
  it('领取不会提前给客服状态操作和回复权限', () => {
    expect(ticketPermissions(ticket, agent)).toMatchObject({ claim: true, start: false, reply: false })
    expect(ticketPermissions({ ...ticket, assignee_id: 2 }, agent)).toMatchObject({ claim: false, start: true, reply: true })
    expect(ticketPermissions({ ...ticket, assignee_id: 9 }, agent)).toMatchObject({ start: false, reply: false })
  })
  it('只允许负责客服解决、创建人重新打开或关闭', () => {
    expect(ticketPermissions({ ...ticket, status: 'in_progress', assignee_id: 2 }, agent).resolve).toBe(true)
    const resolved = { ...ticket, status: 'resolved', assignee_id: 2 }
    expect(ticketPermissions(resolved, user)).toMatchObject({ close: true, reopen: true })
    expect(ticketPermissions(resolved, agent)).toMatchObject({ close: false, reopen: false, resolve: false })
  })
  it('管理员只能分配，所有关闭工单均为只读', () => {
    expect(ticketPermissions(ticket, admin)).toMatchObject({ assign: true, reply: false, start: false, edit: false })
    for (const actor of [user, agent, admin]) expect(Object.values(ticketPermissions({ ...ticket, status: 'closed', assignee_id: 2 }, actor)).every((value) => !value)).toBe(true)
  })
})
describe('认证恢复', () => {
  beforeEach(() => { storage.clear(); vi.clearAllMocks(); setActivePinia(createPinia()) })
  it('刷新时从 token 恢复用户，并合并重复初始化请求', async () => {
    localStorage.setItem('helpflow.access_token', 'saved-token')
    authApi.getCurrentUser.mockResolvedValue({ id: 1, role: 'user' })
    const auth = useAuthStore()
    await Promise.all([auth.initialize(), auth.initialize()])
    expect(authApi.getCurrentUser).toHaveBeenCalledTimes(1)
    expect(auth.isAuthenticated).toBe(true)
  })
  it('无效会话清除 token', async () => {
    localStorage.setItem('helpflow.access_token', 'expired')
    authApi.getCurrentUser.mockRejectedValue({ response: { status: 401 } })
    const auth = useAuthStore(); await auth.initialize()
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem('helpflow.access_token')).toBeNull()
  })
  it.each([undefined, 500, 503])('临时故障 %s 保留 token，恢复后可重试初始化', async (status) => {
    localStorage.setItem('helpflow.access_token', 'valid-token')
    authApi.getCurrentUser.mockRejectedValueOnce({ response: status ? { status } : undefined })
    const auth = useAuthStore()
    await expect(auth.initialize()).rejects.toBeDefined()
    expect(localStorage.getItem('helpflow.access_token')).toBe('valid-token')
    expect(auth.initialized).toBe(false)
    authApi.getCurrentUser.mockResolvedValueOnce({ id: 1, role: 'user' })
    await auth.initialize()
    expect(auth.isAuthenticated).toBe(true)
  })
  it('登录后获取用户失败不会留下半登录会话' , async () => {
    authApi.login.mockResolvedValue({ access_token: 'new-token' })
    authApi.getCurrentUser.mockRejectedValue(new Error('unavailable'))
    const auth = useAuthStore()
    await expect(auth.login({ email: 'test@example.com', password: 'password1' })).rejects.toThrow()
    expect(auth.token).toBeNull()
  })
})
it('日期缺失或非法时展示占位符', () => { expect(formatDate(null)).toBe('—'); expect(formatDate('invalid')).toBe('—') })

describe('路由角色守卫', () => {
  it('实际路由表可匹配创建页和三种角色详情，未知地址进入 404', () => {
    const router = createRouter({ history: createMemoryHistory(), routes })
    expect(router.resolve('/user/tickets/create').meta.title).toBe('创建工单')
    for (const role of ['user', 'agent', 'admin']) {
      const route = router.resolve(`/${role}/tickets/12`)
      expect(route.meta.roles).toEqual([role])
      expect(route.params.id).toBe('12')
    }
    expect(router.resolve('/user/tickets/invalid').meta.status).toBe('404')
  })
  it('未登录访问深层链接时保留目标地址', () => {
    expect(routeAccess({ path: '/user/tickets/12', fullPath: '/user/tickets/12', meta: { requiresAuth: true, roles: ['user'] } }, { isAuthenticated: false })).toEqual({ path: '/login', query: { redirect: '/user/tickets/12' } })
  })
  it('每种角色首页与直接越权访问', () => {
    for (const role of ['user', 'agent', 'admin']) {
      const auth = { role, isAuthenticated: true }
      expect(routeAccess({ path: '/', meta: {} }, auth)).toBe(`/${role}/dashboard`)
      for (const target of ['user', 'agent', 'admin']) {
        expect(routeAccess({ path: `/${target}/tickets`, meta: { requiresAuth: true, roles: [target] } }, auth)).toBe(role === target ? true : '/403')
      }
    }
  })
})
