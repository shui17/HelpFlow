import { describe, expect, it } from 'vitest'
import { slaListTarget } from '../src/utils/sla.js'

describe('首页 SLA 筛选跳转保持角色范围', () => {
  for (const role of ['user', 'agent', 'admin']) {
    it(`${role} 进入自己的列表并保留筛选`, () => {
      for (const sla of ['due_soon', 'overdue']) {
        expect(slaListTarget(role, sla)).toEqual({
          path: role === 'agent' ? '/agent/tickets/mine' : `/${role}/tickets`, query: { sla },
        })
      }
    })
  }
})
