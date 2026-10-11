# HelpFlow 前端设计文档

## 1 文档信息

| 项目 | 内容 |
| --- | --- |
| 项目名称 | HelpFlow 客服工单管理系统 |
| 文档类型 | 前端详细设计 |
| 文档版本 | V1.0 |
| 编写日期 | 2026-10-04 |
| 上游文档 | `docs/requirements-confirmation.md`、`docs/prd.md` |
| 前端技术 | Vue 3、Vite、JavaScript、Vue Router、Pinia、Axios、Element Plus |

## 2 文档目的

本文档用于指导 HelpFlow 前端框架搭建和页面实现，明确前端目录、路由、布局、组件、状态管理、接口封装、页面交互和阶段验收。

本文档只描述前端如何组织和实现，不重复解释业务背景，不规定后端内部实现，也不包含学习路线。

## 3 前端目标与边界

### 3.1 前端目标

- 为普通用户、客服和管理员提供可操作的浏览器页面。
- 根据登录状态和角色控制路由、菜单和按钮。
- 通过 Axios 调用 `/api/v1` 后端接口。
- 统一处理 Token、加载状态、错误提示和空数据。
- 使用一致的表单、表格、分页、标签和确认弹窗。
- 不依赖 Swagger 完成任何核心业务操作。

### 3.2 前端不负责

- 判断最终业务权限。
- 直接访问 MySQL。
- 生成可信的创建人、负责人和操作人。
- 决定工单状态是否合法。
- 保证并发领取只能有一个客服成功。
- 保存密码和敏感配置。

上述规则由后端最终校验。前端隐藏无权限按钮只用于改善体验，不能替代后端权限控制。

## 4 前端技术设计

| 技术 | 使用方式 |
| --- | --- |
| Vue 3 | 使用 Composition API 和单文件组件 |
| Vite | 创建项目、开发服务器和生产构建 |
| JavaScript | 当前版本不使用 TypeScript |
| Vue Router | 页面路由、登录守卫和角色守卫 |
| Pinia | 只管理认证相关全局状态 |
| Axios | 请求封装、Token 注入和响应错误处理 |
| Element Plus | 表单、表格、分页、标签、对话框和消息提示 |

当前不引入额外 UI 框架、复杂图表库、CSS 预处理器和请求状态库。

## 5 前端目录结构

```text
frontend/
├── public/
├── src/
│   ├── api/
│   │   ├── auth.js
│   │   ├── tickets.js
│   │   ├── users.js
│   │   └── dashboard.js
│   ├── assets/
│   │   └── styles/
│   │       ├── reset.css
│   │       ├── variables.css
│   │       └── global.css
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppEmpty.vue
│   │   │   ├── AppLoading.vue
│   │   │   ├── AppPagination.vue
│   │   │   └── ConfirmAction.vue
│   │   └── ticket/
│   │       ├── TicketFilters.vue
│   │       ├── TicketInfoCard.vue
│   │       ├── TicketStatusTag.vue
│   │       ├── TicketPriorityTag.vue
│   │       ├── TicketCommentList.vue
│   │       ├── TicketCommentForm.vue
│   │       └── TicketTimeline.vue
│   ├── constants/
│   │   ├── roles.js
│   │   └── tickets.js
│   ├── layouts/
│   │   ├── AuthLayout.vue
│   │   └── MainLayout.vue
│   ├── router/
│   │   ├── index.js
│   │   └── routes.js
│   ├── stores/
│   │   └── auth.js
│   ├── utils/
│   │   ├── request.js
│   │   ├── token.js
│   │   ├── datetime.js
│   │   └── error.js
│   ├── views/
│   │   ├── auth/
│   │   │   ├── LoginView.vue
│   │   │   └── RegisterView.vue
│   │   ├── common/
│   │   │   ├── ProfileView.vue
│   │   │   ├── ChangePasswordView.vue
│   │   │   ├── ForbiddenView.vue
│   │   │   └── NotFoundView.vue
│   │   ├── user/
│   │   │   ├── UserDashboardView.vue
│   │   │   ├── UserTicketListView.vue
│   │   │   ├── UserTicketCreateView.vue
│   │   │   └── UserTicketDetailView.vue
│   │   ├── agent/
│   │   │   ├── AgentDashboardView.vue
│   │   │   ├── UnassignedTicketListView.vue
│   │   │   ├── AgentTicketListView.vue
│   │   │   └── AgentTicketDetailView.vue
│   │   └── admin/
│   │       ├── AdminDashboardView.vue
│   │       ├── AdminTicketListView.vue
│   │       ├── AdminTicketDetailView.vue
│   │       └── UserManagementView.vue
│   ├── App.vue
│   └── main.js
├── .env.example
├── index.html
├── package.json
└── vite.config.js
```

### 5.1 目录约束

- `views` 负责页面级数据获取和业务交互。
- `components` 只保存可复用组件，不创建只有几行模板的无意义组件。
- `api` 只封装接口路径和请求方法，不显示消息提示。
- `stores` 只保存真正跨页面共享的认证状态。
- `utils/request.js` 是唯一创建 Axios 实例的位置。
- `constants` 统一保存角色、状态、分类和优先级映射。
- 页面不能在组件中硬编码后端基础地址。

## 6 环境变量

前端 `.env.example` 至少包含：

```text
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

规则：

- 业务代码通过 `import.meta.env.VITE_API_BASE_URL` 获取地址。
- 不把数据库连接、JWT 密钥和管理员密码放入前端环境变量。
- 前端环境变量不能被视为秘密，因为构建后会被浏览器读取。

## 7 应用启动流程

```text
main.js 创建 Vue 应用
    ↓
注册 Pinia、Vue Router 和 Element Plus
    ↓
路由守卫读取本地 Token
    ↓
存在 Token 且用户信息尚未恢复
    ↓
调用 GET /auth/me
    ├── 成功：保存当前用户，继续进入目标页面
    └── 失败：清除 Token，跳转登录页
```

`App.vue` 只作为应用根节点和路由出口，不堆积页面业务逻辑。

## 8 认证状态设计

### 8.1 `authStore` 状态

```text
token                 当前 Access Token
currentUser           当前用户对象
initialized           是否完成登录状态恢复
```

派生状态：

```text
isAuthenticated       是否已登录
role                  当前角色
isUser                是否普通用户
isAgent               是否客服
isAdmin               是否管理员
```

### 8.2 `authStore` 操作

- `register(payload)`：注册普通用户。
- `login(payload)`：登录、保存 Token、获取当前用户。
- `fetchCurrentUser()`：调用 `/auth/me` 恢复用户信息。
- `changePassword(payload)`：修改密码后退出。
- `logout()`：清除 Store 和本地 Token。
- `initialize()`：应用启动时恢复认证状态。

### 8.3 Token 工具

`utils/token.js` 只负责：

- 读取 Token
- 保存 Token
- 删除 Token

Token 使用一个固定的 `localStorage` 键名。任何页面不得直接重复操作 `localStorage`。

## 9 Axios 请求设计

### 9.1 Axios 实例

`utils/request.js` 创建一个 Axios 实例：

- `baseURL` 来自环境变量。
- 设置合理超时时间。
- 默认请求和响应类型为 JSON。

### 9.2 请求拦截器

- 如果存在 Token，添加 `Authorization: Bearer <token>`。
- 不在控制台打印 Token、密码和完整登录请求。

### 9.3 响应拦截器

- 成功时返回响应中的 `data` 结构，页面无需重复读取多层字段。
- `401` 时清除认证状态并跳转登录页。
- `403` 时显示无权限提示。
- `404` 时显示数据不存在。
- `409` 时保留后端冲突信息，由页面决定是否刷新。
- 网络错误显示“无法连接服务器，请检查后端是否启动”。
- 未知错误显示“系统暂时不可用”。

避免在拦截器和页面中同时显示同一个错误两次。表单字段错误由页面处理，通用错误由拦截器或统一错误工具处理。

## 10 API 模块设计

### 10.1 `api/auth.js`

- `register(data)`
- `login(data)`
- `getCurrentUser()`
- `changePassword(data)`

### 10.2 `api/tickets.js`

- `createTicket(data)`
- `getTickets(params)`
- `getTicketDetail(id)`
- `updateTicket(id, data)`
- `cancelTicket(id)`
- `claimTicket(id)`
- `assignTicket(id, data)`
- `changeTicketStatus(id, data)`
- `getTicketComments(id)`
- `createTicketComment(id, data)`
- `getTicketActivities(id)`

### 10.3 `api/users.js`

- `getUsers(params)`
- `getUserDetail(id)`
- `changeUserRole(id, data)`
- `changeUserStatus(id, data)`

### 10.4 `api/dashboard.js`

- `getDashboardSummary()`

每个函数只负责请求，不直接操作路由、Store、弹窗或页面组件。

## 11 路由设计

### 11.1 路由表

| 路径 | 页面 | 登录要求 | 角色 |
| --- | --- | --- | --- |
| `/login` | 登录 | 否 | 全部 |
| `/register` | 注册 | 否 | 全部 |
| `/profile` | 个人中心 | 是 | 全部 |
| `/change-password` | 修改密码 | 是 | 全部 |
| `/user/dashboard` | 用户概览 | 是 | `user` |
| `/user/tickets` | 我的工单 | 是 | `user` |
| `/user/tickets/create` | 创建工单 | 是 | `user` |
| `/user/tickets/:id` | 用户工单详情 | 是 | `user` |
| `/agent/dashboard` | 客服工作台 | 是 | `agent` |
| `/agent/tickets/unassigned` | 待领取工单 | 是 | `agent` |
| `/agent/tickets/mine` | 我负责的工单 | 是 | `agent` |
| `/agent/tickets/:id` | 客服工单详情 | 是 | `agent` |
| `/admin/dashboard` | 管理概览 | 是 | `admin` |
| `/admin/tickets` | 全部工单 | 是 | `admin` |
| `/admin/tickets/:id` | 管理员工单详情 | 是 | `admin` |
| `/admin/users` | 用户管理 | 是 | `admin` |
| `/403` | 无权限 | 否 | 全部 |
| `/:pathMatch(.*)*` | 页面不存在 | 否 | 全部 |

### 11.2 路由元信息

受保护路由使用元信息：

```text
requiresAuth          是否要求登录
roles                 允许的角色数组
title                 页面标题
```

### 11.3 路由守卫

判断顺序：

```text
是否完成认证初始化
    ↓
目标页面是否要求登录
    ↓
当前是否已登录
    ↓
当前角色是否在允许列表
    ↓
允许进入或跳转到登录页/403
```

登录用户访问 `/login` 或 `/register` 时，根据角色跳转到自己的 Dashboard。

## 12 布局与菜单设计

### 12.1 `AuthLayout`

用于登录和注册页面，包含：

- 系统名称
- 简短说明
- 居中表单卡片
- 登录和注册链接

### 12.2 `MainLayout`

包含：

- 顶部栏：系统名称、当前用户名、角色名称、退出按钮。
- 左侧菜单：根据当前角色显示。
- 主内容区：渲染子路由页面。
- 折叠菜单：只需支持桌面端基础折叠，不做复杂响应式导航。

### 12.3 角色菜单

普通用户：

```text
概览
我的工单
创建工单
个人中心
```

客服：

```text
工作台
待领取工单
我负责的工单
个人中心
```

管理员：

```text
管理概览
全部工单
用户管理
个人中心
```

## 13 常量与显示映射

### 13.1 角色

```text
user    → 普通用户
agent   → 客服
admin   → 管理员
```

### 13.2 工单状态

```text
open          → 待处理
in_progress   → 处理中
resolved      → 已解决
closed        → 已关闭
```

### 13.3 优先级

```text
low       → 低
normal    → 普通
high      → 高
urgent    → 紧急
```

### 13.4 分类

```text
account       → 账号问题
product       → 产品问题
payment       → 支付问题
technical     → 技术问题
other         → 其他
```

映射和标签颜色集中定义，页面不得重复维护不同版本。

## 14 公共组件设计

### 14.1 `AppLoading`

用于首次加载或局部请求，不覆盖整个浏览器页面，避免用户误以为页面卡死。

### 14.2 `AppEmpty`

用于列表为空、暂无回复和暂无时间线数据，允许传入说明文字和可选操作按钮。

### 14.3 `AppPagination`

统一接收当前页、每页数量和总数，并发出页码变化事件。默认每页 10 条。

### 14.4 `ConfirmAction`

封装危险操作确认，适用于撤销、关闭、领取、重新分配、禁用和角色调整。

### 14.5 `TicketFilters`

支持状态、优先级、分类、关键词和排序。管理员版本可以增加负责人筛选。筛选变化由父页面决定何时请求。

### 14.6 `TicketInfoCard`

显示工单编号、标题、描述、分类、优先级、状态、创建人、负责人和时间。

### 14.7 `TicketCommentList` 与 `TicketCommentForm`

- 列表区分当前用户和对方回复。
- 回复表单只接受纯文本。
- 提交中禁用重复提交。
- 已关闭或无权限时隐藏表单并显示原因。

### 14.8 `TicketTimeline`

按时间顺序显示创建、领取、分配、状态变化、重新打开、撤销和关闭事件。

## 15 页面详细设计

### 15.1 登录页

字段：邮箱、密码。

行为：

- 校验必填和邮箱格式。
- 防止提交过程中重复点击。
- 登录成功后获取当前用户并按角色跳转。
- 登录失败只显示“邮箱或密码错误”或后端统一信息。

### 15.2 注册页

字段：用户名、邮箱、密码、确认密码。

校验：

- 用户名 2～30 个字符。
- 邮箱格式正确。
- 密码 8～64 个字符且至少包含一个字母和一个数字。
- 两次密码一致。

注册成功后跳转登录页，不自动赋予客服或管理员角色。

### 15.3 用户概览

显示当前用户 `open`、`in_progress`、`resolved`、`closed` 工单数量，并提供“创建工单”和“查看我的工单”入口。

### 15.4 我的工单列表

展示：工单编号、标题、分类、优先级、状态、负责人、创建时间。

支持：

- 分页
- 状态筛选
- 优先级筛选
- 分类筛选
- 标题或编号搜索
- 创建时间排序
- 清空筛选
- 点击进入详情

### 15.5 创建工单页

字段：标题、问题描述、分类、优先级。

要求：

- 前端进行必填和长度校验。
- 创建中禁用提交。
- 创建成功后跳转工单详情。
- 不允许前端填写创建人、状态和负责人。

### 15.6 用户工单详情

区域：

- 工单基本信息
- 当前状态与负责人
- 可用操作按钮
- 回复区
- 处理时间线

按钮规则：

- `open` 且无人负责：显示编辑和撤销。
- `resolved`：显示“确认关闭”和“重新打开”。
- `closed`：不显示编辑、撤销和回复输入。

### 15.7 客服工作台

显示：待领取数量、本人处理中数量、本人已解决数量，并提供对应列表入口。

### 15.8 待领取工单列表

只显示 `open` 且负责人为空的工单。每行提供查看详情和领取按钮。

领取流程：

- 二次确认。
- 提交中禁用按钮。
- 成功后从待领取列表移除并提示成功。
- `409` 时提示已被领取并刷新列表。

### 15.9 客服负责工单列表

只显示当前客服负责的工单，支持状态、优先级、分类、关键词和时间排序。

### 15.10 客服工单详情

区域与普通用户详情一致，但操作按钮不同：

- `open` 且当前客服是负责人：显示“开始处理”。
- `in_progress` 且当前客服是负责人：显示“标记为已解决”。
- 未关闭且当前客服是负责人：显示回复输入。
- `resolved`：等待用户确认，不允许客服直接关闭。
- `closed`：只读。

### 15.11 管理概览

显示全局各状态工单数、启用普通用户数和启用客服数，并提供全部工单与用户管理入口。

### 15.12 管理员工单列表

展示所有工单，支持状态、优先级、分类、负责人、关键词和创建时间排序。

### 15.13 管理员工单详情

显示工单基本信息、回复和时间线。允许：

- 给未关闭工单选择启用客服。
- 重新分配非关闭工单。
- 查看分配前后的负责人变化。

管理员不显示回复输入和绕过流程的状态按钮。

### 15.14 用户管理页

展示：用户名、邮箱、角色、账号状态、注册时间和操作。

支持：

- 用户名或邮箱搜索
- 角色筛选
- 启用状态筛选
- 分页
- 普通用户与客服角色调整
- 账号启用和禁用

限制：

- 管理员不能禁用自己。
- 管理员账号不显示角色修改按钮。
- 操作前二次确认。
- 后端拒绝有未关闭负责工单的客服降级或禁用时，显示原因并保持原数据。

### 15.15 个人中心

显示当前用户名、邮箱、角色、账号状态和注册时间。当前版本不提供修改用户名和邮箱。

### 15.16 修改密码页

字段：当前密码、新密码、确认新密码。修改成功后清除认证信息并返回登录页。

## 16 表单与交互规范

- 所有必填字段显示必填标识。
- 前端校验用于快速反馈，后端错误仍必须正确显示。
- 提交期间禁用重复提交。
- 成功提示使用简洁文字，不显示内部数据。
- 危险操作使用确认弹窗，并说明影响。
- 列表筛选后默认回到第一页。
- 删除筛选条件后重新请求列表。
- 页面离开时不保留未提交密码。
- 工单正文和回复以纯文本展示，避免直接渲染不可信 HTML。

## 17 页面数据状态

每个请求页面至少维护：

```text
loading             首次或刷新加载
submitting          表单或动作提交
data                当前业务数据
error               当前错误，可为空
```

列表额外维护：

```text
filters             筛选条件
page                当前页
pageSize            每页数量
total               总数量
items               当前页数据
```

详情页中的工单、回复和时间线可以分别加载，但页面需要避免同一动作被重复触发。

## 18 日期和文本显示

- 后端返回 ISO 8601 时间字符串。
- 前端统一格式化为 `YYYY-MM-DD HH:mm:ss`。
- 所有页面使用同一个日期格式化工具。
- 空负责人显示“暂未分配”。
- 空列表显示明确说明，不显示空白页面。
- 长描述保持换行并避免撑破布局。

## 19 前端阶段安排

### 前端阶段 1：基础框架

- 初始化 Vue、Router、Pinia、Axios 和 Element Plus。
- 建立目录、全局样式、环境变量和请求实例。
- 创建健康检查页面或启动状态提示。

验收：前端启动并成功访问后端健康检查。

### 前端阶段 2：认证

- 完成登录、注册、个人中心和修改密码。
- 完成认证 Store、Token 工具、拦截器和路由守卫。
- 完成 AuthLayout 和 MainLayout。

验收：不同角色登录后进入正确页面，刷新后可恢复登录状态。

### 前端阶段 3：普通用户工单

- 完成用户概览、工单列表、创建和详情。
- 完成筛选、分页、编辑和撤销。

验收：普通用户能通过页面管理自己的未处理工单。

### 前端阶段 4：客服和管理员工单

- 完成待领取、客服负责列表和客服详情。
- 完成管理员工单列表、详情、分配和重新分配。

验收：领取冲突能正确提示，管理员可以分配工单。

### 前端阶段 5：回复、状态和时间线

- 完成回复组件、状态操作和时间线。
- 根据角色和状态显示正确按钮。

验收：浏览器中可以完成从处理中到关闭的完整流程。

### 前端阶段 6：用户管理和概览

- 完成用户管理页面。
- 完成三种角色概览数据。

验收：角色调整、启用和禁用的反馈正确。

### 前端阶段 7：联调与整理

- 统一加载、错误、成功和空数据状态。
- 检查路由、菜单、表单、弹窗和常见分辨率。

验收：需求确认书中的所有前端页面和交互通过。

## 20 前端完成标准

- [ ] 所有规划页面均可访问。
- [ ] 未登录和角色越权路由被拦截。
- [ ] Token 失效后能够返回登录页。
- [ ] Axios 统一携带 Token 和处理通用错误。
- [ ] 页面不直接硬编码 API 基础地址。
- [ ] 三种角色只看到适合自己的菜单和按钮。
- [ ] 工单列表具有分页、筛选、搜索和排序。
- [ ] 工单详情具有信息、回复和时间线。
- [ ] 危险操作具有二次确认。
- [ ] 领取冲突能够提示并刷新数据。
- [ ] 加载、空数据和错误状态完整。
- [ ] 页面不依赖 Swagger 完成业务操作。
- [ ] 常见笔记本分辨率下无明显布局错误。

## 21 与后端文档的边界

前端文档确定页面需要什么数据和操作，但以下内容以后端设计文档为准：

- 接口的精确请求与响应字段
- 业务错误码
- 权限判断和状态流转结果
- 数据库字段和约束
- 事务和并发实现

前后端出现不一致时，先检查需求确认书和 PRD，再同步修改两份设计文档，不在代码中临时采用互相矛盾的约定。
