import { test, expect } from '@playwright/test'

test('回复助手：未配置、无资料、来源与人工采用发送', async ({ page, request }) => {
  const base = 'http://127.0.0.1:8011/api/v1'
  const password = process.env.E2E_PASSWORD || 'BrowserTest123'
  const email = `rag-${Date.now()}@example.com`
  expect((await request.post(`${base}/auth/register`, { data: { username: '知识测试', email, password, confirm_password: password } })).status()).toBe(201)
  const auth = (await (await request.post(`${base}/auth/login`, { data: { email, password } })).json()).data
  const userHeaders = { Authorization: `Bearer ${auth.access_token}` }
  const ticket = (await (await request.post(`${base}/tickets`, { headers: userHeaders, data: { title: '登录失败排查', description: '登录失败该怎么办' } })).json()).data
  const agent = (await (await request.post(`${base}/auth/login`, { data: { email: 'browser-agent@example.com', password } })).json()).data
  expect((await request.post(`${base}/tickets/${ticket.id}/claim`, { headers: { Authorization: `Bearer ${agent.access_token}` } })).status()).toBe(200)
  await page.goto('/login')
  await page.getByLabel('邮箱', { exact: true }).fill('browser-agent@example.com')
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/dashboard/)
  await page.goto(`/agent/tickets/${ticket.id}`)
  const panel = page.getByRole('region', { name: 'AI 回复助手' })
  await panel.getByRole('button', { name: '生成回复建议' }).click()
  await expect(panel).toContainText('AI 服务尚未配置')
  // 下列响应仅为浏览器交互替身；不代表真实模型验证。
  let mode = 'empty'
  await page.route(`**/tickets/${ticket.id}/reply-suggestion`, async route => {
    await route.fulfill({ json: { code: 0, data: mode === 'empty'
      ? { status: 'insufficient_evidence', draft: '', sources: [] }
      : { status: 'ok', draft: '请先核对注册邮箱。', sources: [{ chunk_id: 'test', title: '登录失败排查', version: 1, content: '登录使用注册邮箱和密码。' }] } } })
  })
  await panel.getByRole('button', { name: '重新生成建议' }).click()
  await expect(panel).toContainText('知识资料不足')
  mode = 'ok'
  await panel.getByRole('button', { name: '生成回复建议' }).click()
  await expect(panel).toContainText('请先核对注册邮箱。')
  await panel.locator('summary').click()
  await expect(panel).toContainText('登录使用注册邮箱和密码。')
  const editor = page.getByPlaceholder('请输入回复内容，支持纯文本。')
  await expect(editor).toHaveValue('')
  await editor.fill('手动输入不能丢失')
  await panel.getByRole('button', { name: '采用草稿到回复框' }).click()
  await page.locator('.el-message-box').getByRole('button', { name: '取消', exact: true }).click()
  await expect(editor).toHaveValue('手动输入不能丢失')
  await panel.getByRole('button', { name: '采用草稿到回复框' }).click()
  await page.locator('.el-message-box').getByRole('button', { name: '确认', exact: true }).click()
  await expect(editor).toHaveValue('请先核对注册邮箱。')
  expect((await (await request.get(`${base}/tickets/${ticket.id}/comments`, { headers: userHeaders })).json()).data).toEqual([])
  await page.getByRole('button', { name: '发送回复', exact: true }).click()
  await expect(editor).toHaveValue('')
  await expect(page.getByText('请先核对注册邮箱。', { exact: true })).toBeVisible()
})
