const dashboard = () => import('../views/DashboardView.vue')
const tickets = () => import('../views/TicketListView.vue')
const detail = () => import('../views/TicketDetailView.vue')
const protectedRoute = (path, component, title, roles, extra = {}) => ({ path, component, meta: { requiresAuth: true, title, roles, ...extra } })
export const routes = [
  { path: '/session-unavailable', component: () => import('../views/SessionUnavailableView.vue'), meta: { title: '连接暂时不可用' } },
  { path: '/login', component: () => import('../views/AuthView.vue'), meta: { title: '登录', guest: true } },
  { path: '/register', component: () => import('../views/AuthView.vue'), meta: { title: '注册', guest: true } },
  { path: '/', component: () => import('../layouts/MainLayout.vue'), children: [
    ...['user', 'agent', 'admin'].flatMap((role) => [
      protectedRoute(`${role}/dashboard`, dashboard, { user: '概览', agent: '客服工作台', admin: '管理概览' }[role], [role]),
      protectedRoute(`${role}/tickets/:id(\\d+)`, detail, '工单详情', [role]),
    ]),
    protectedRoute('user/tickets', tickets, '我的工单', ['user']),
    protectedRoute('user/tickets/create', () => import('../views/TicketCreateView.vue'), '创建工单', ['user']),
    protectedRoute('agent/tickets/unassigned', tickets, '待领取工单', ['agent'], { scope: 'unassigned' }),
    protectedRoute('agent/tickets/mine', tickets, '我负责的工单', ['agent'], { scope: 'mine' }),
    protectedRoute('admin/tickets', tickets, '全部工单', ['admin']),
    protectedRoute('admin/users', () => import('../views/UserManagementView.vue'), '用户管理', ['admin']),
    protectedRoute('profile', () => import('../views/ProfileView.vue'), '个人中心'),
    protectedRoute('notifications', () => import('../views/NotificationsView.vue'), '站内通知'),
    protectedRoute('change-password', () => import('../views/ChangePasswordView.vue'), '修改密码'),
  ] },
  { path: '/403', component: () => import('../views/ErrorView.vue'), meta: { title: '无访问权限', status: '403' } },
  { path: '/:pathMatch(.*)*', component: () => import('../views/ErrorView.vue'), meta: { title: '页面不存在', status: '404' } },
]
