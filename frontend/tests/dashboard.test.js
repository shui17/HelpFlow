import { describe, it, expect, vi } from 'vitest'
vi.mock('../src/utils/request.js', () => ({ default: { get: vi.fn() } }))
const { default: request } = await import('../src/utils/request.js')
const { getDashboardSummary } = await import('../src/api/dashboard.js')
describe('概览统计', () => {
  it('使用一次后端聚合请求，不遍历工单分页', async () => {
    const summary = { counts: { open: 200 }, recent: [{ id: 1000 }] }
    request.get.mockResolvedValue(summary)
    expect(await getDashboardSummary({ role: 'admin' })).toEqual(summary)
    expect(request.get).toHaveBeenCalledExactlyOnceWith('/tickets/summary')
  })
})
