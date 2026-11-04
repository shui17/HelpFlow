import { test, expect } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
const password = process.env.E2E_PASSWORD || 'BrowserTest123'
async function login(page, email) {
  await page.goto('/login')
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/dashboard/)
}
async function confirm(page) {
  await page.locator('.el-message-box').getByRole('button', { name: '确认', exact: true }).click()
}

test('阶段13 SLA 筛选、升级记录及晚响应展示', async ({ page, browser, request }) => {
  const api = 'http://127.0.0.1:8011/api/v1'
  const email = `sla-${Date.now()}@example.com`
  expect((await request.post(`${api}/auth/register`, { data: {
    username: '时限测试用户', email, password, confirm_password: password,
  } })).status()).toBe(201)
  const session = (await (await request.post(`${api}/auth/login`, { data: { email, password } })).json()).data
  const headers = { Authorization: `Bearer ${session.access_token}` }
  const created = await request.post(`${api}/tickets`, { headers, data: { title: '阶段13时限演示', description: '首次响应超时后仍保留逾期事实' } })
  expect(created.status()).toBe(201)
  const ticket = (await created.json()).data
  expect(ticket.sla.state).toBe('waiting')
  // 只调整 Playwright 已校验的独立测试库，走真实扫描器与事务通知。
  const python = resolve('../backend/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  execFileSync(python, ['-c', `
import asyncio, os, sys
from sqlalchemy.engine import make_url
from datetime import timedelta
from app.config import Settings
from app.db.base import utcnow
from app.db.session import create_database
from app.models import TicketSLA
from app.sla_scheduler import SLAIndex
from scripts.scan_sla import Scanner
async def run():
    url = os.environ['HELPFLOW_TEST_DATABASE_URL']
    assert (make_url(url).database or '').startswith('helpflow_stage5_test')
    engine, factory = create_database(url)
    index = SLAIndex(Settings(_env_file=None, redis_url=None))
    try:
        async with factory() as session, session.begin():
            row = await session.get(TicketSLA, int(sys.argv[1]))
            row.due_at = utcnow() - timedelta(seconds=10)
        stats = dict(processed=0, events=0, failed=0, max_detection_delay_seconds=0)
        await Scanner(factory, index).process(int(sys.argv[1]), 1, stats)
        assert stats['events'] == 1 and stats['failed'] == 0
    finally:
        await index.close()
        await engine.dispose()
asyncio.run(run())
`, String(ticket.id)], { cwd: resolve('../backend'), env: process.env, timeout: 20000 })
  await login(page, email)
  await page.getByRole('link', { name: '查看已超时 →', exact: true }).click()
  await expect(page).toHaveURL(/user\/tickets\?sla=overdue$/)
  await page.getByRole('link', { name: '阶段13时限演示', exact: true }).click()
  const panel = page.locator('section.panel').filter({ has: page.getByRole('heading', { name: '首次响应时限', exact: true }) })
  await expect(panel.getByText('已超时', { exact: true })).toBeVisible()
  await expect(panel.getByText(/超时升级 ·/)).toBeVisible()
  await expect(panel.getByText('尚未响应', { exact: true })).toBeVisible()
  const context = await browser.newContext()
  try {
    const agent = await context.newPage()
    await login(agent, 'browser-agent@example.com')
    await agent.goto(`/agent/tickets/${ticket.id}`)
    await agent.getByRole('button', { name: '领取工单', exact: true }).click(); await confirm(agent)
    await agent.getByLabel('添加回复', { exact: true }).fill('首次响应虽晚，升级记录仍保留')
    await agent.getByRole('button', { name: '发送回复', exact: true }).click()
    await expect(agent.getByText('首次响应虽晚，升级记录仍保留', { exact: true })).toBeVisible()
    await page.reload()
    await expect(panel.getByText('尚未响应', { exact: true })).toHaveCount(0)
    await expect(panel.getByText('已超时', { exact: true })).toBeVisible()
    await expect(panel.getByText(/超时升级 ·/)).toHaveCount(1)
    await page.screenshot({ path: resolve('../.local/stage13-sla-detail.png'), fullPage: true })
  } finally { await context.close() }
})
test('三角色工单闭环和临时故障会话恢复', async ({ page, browser }) => {
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  const email = `browser-${Date.now()}@example.com`
  await page.goto('/register')
  await page.getByLabel('用户名', { exact: true }).fill('浏览器用户')
  await page.getByLabel('邮箱', { exact: true }).fill(email)
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByLabel('确认密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '创建账号', exact: true }).click()
  await expect(page).toHaveURL(/login/)
  await login(page, email)
  const token = await page.evaluate(() => localStorage.getItem('helpflow.access_token'))
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }))
  await page.reload()
  await expect(page.getByText('暂时无法恢复登录状态', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => localStorage.getItem('helpflow.access_token'))).toBe(token)
  await page.unroute('**/api/v1/auth/me')
  await page.getByRole('button', { name: '重新连接', exact: true }).click()
  await expect(page).toHaveURL(/dashboard/)
  await page.goto('/user/tickets/create')
  await page.getByLabel('工单标题', { exact: true }).fill(`浏览器闭环 ${Date.now()}`)
  await page.getByLabel('问题描述', { exact: true }).fill('自动验证创建、领取、回复、解决与关闭')
  await page.getByRole('button', { name: '提交工单', exact: true }).click()
  await expect(page).toHaveURL(/user\/tickets\/\d+$/)
  const id = page.url().split('/').pop()
  const agentContext = await browser.newContext()
  const agent = await agentContext.newPage()
  await login(agent, 'browser-agent@example.com')
  await agent.goto(`/agent/tickets/${id}`)
  await agent.getByRole('button', { name: '领取工单', exact: true }).click(); await confirm(agent)
  await agent.getByRole('button', { name: '开始处理', exact: true }).click(); await confirm(agent)
  await agent.getByLabel('添加回复', { exact: true }).fill('已经定位并修复问题')
  await agent.getByRole('button', { name: '发送回复', exact: true }).click()
  await expect(agent.getByText('已经定位并修复问题', { exact: true })).toBeVisible()
  await agent.getByRole('button', { name: '标记为已解决', exact: true }).click(); await confirm(agent)
  await page.reload()
  await page.getByRole('button', { name: '确认关闭', exact: true }).click(); await confirm(page)
  await expect(page.getByText('工单已关闭，无法继续回复。', { exact: true })).toBeVisible()
  const adminContext = await browser.newContext()
  const admin = await adminContext.newPage()
  await login(admin, 'browser-admin@example.com')
  await admin.goto(`/admin/tickets/${id}`)
  await expect(admin.getByText('已经定位并修复问题', { exact: true })).toBeVisible()
  await expect(admin.getByText('处理时间线', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
  await agentContext.close(); await adminContext.close()
})

test('阶段12内部备注、转交和站内通知闭环', async ({ page, browser, request }) => {
  const email = `collaboration-${Date.now()}@example.com`
  const api = 'http://127.0.0.1:8011/api/v1'
  const registration = await request.post(`${api}/auth/register`, { data: {
    username: '协作用户', email, password, confirm_password: password,
  } })
  expect(registration.status()).toBe(201)
  const session = await request.post(`${api}/auth/login`, { data: { email, password } })
  const headers = { Authorization: `Bearer ${(await session.json()).data.access_token}` }
  const created = await request.post(`${api}/tickets`, { headers, data: { title: '阶段12协作演示', description: '内部诊断与团队转交' } })
  expect(created.status()).toBe(201)
  const id = (await created.json()).data.id
  await login(page, 'browser-agent@example.com')
  await page.goto(`/agent/tickets/${id}`)
  await page.getByRole('button', { name: '领取工单', exact: true }).click(); await confirm(page)
  await page.getByLabel('添加内部备注', { exact: true }).fill('内部诊断：请二线客服接手')
  await page.getByRole('button', { name: '保存内部备注', exact: true }).click()
  await expect(page.getByText('内部诊断：请二线客服接手', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: '转交工单', exact: true }).click()
  await page.getByRole('combobox', { name: '目标客服', exact: true }).fill('转交客服')
  await page.getByRole('option', { name: /转交客服/ }).click()
  await page.getByLabel('转交原因', { exact: true }).fill('交由二线跟进')
  await page.getByRole('button', { name: '确认转交', exact: true }).click(); await confirm(page)
  await expect(page).toHaveURL(/agent\/tickets\/mine$/)
  await page.goto(`/agent/tickets/${id}`)
  await expect(page.getByText('无权查看或操作该工单', { exact: true })).toBeVisible()
  const secondContext = await browser.newContext()
  try {
    const second = await secondContext.newPage()
    await login(second, 'browser-agent2@example.com')
    await second.goto('/notifications')
    await expect(second.getByText(`您有一张新分配或转交的工单 · #${id}`, { exact: true })).toBeVisible()
    await second.getByRole('button', { name: '查看工单', exact: true }).first().click()
    await expect(second).toHaveURL(new RegExp(`/agent/tickets/${id}$`))
    await expect(second.getByText('内部诊断：请二线客服接手', { exact: true })).toBeVisible()
    await second.getByRole('button', { name: '开始处理', exact: true }).click(); await confirm(second)
    await second.getByLabel('添加回复', { exact: true }).fill('二线已经处理完成')
    await second.getByRole('button', { name: '发送回复', exact: true }).click()
    await expect(second.getByText('二线已经处理完成', { exact: true })).toBeVisible()
    await second.getByRole('button', { name: '标记为已解决', exact: true }).click(); await confirm(second)
    await page.getByRole('button', { name: '退出', exact: true }).click()
    await login(page, email)
    await page.goto('/notifications')
    await expect(page.getByText(`您的工单有一条新的公开回复 · #${id}`, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '查看工单', exact: true }).first().click()
    await expect(page.getByText('内部诊断：请二线客服接手', { exact: true })).toHaveCount(0)
    await expect(page.getByText('内部备注', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '确认关闭', exact: true }).click(); await confirm(page)
    await expect(page.getByText('工单已关闭，无法继续回复。', { exact: true })).toBeVisible()
  } finally { await secondContext.close() }
})
