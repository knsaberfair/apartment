# 公寓管理系统

基于 **Vue 3 + Vite + TypeScript + Tailwind CSS**、**Python + FastAPI** 和 **微信小程序** 的公寓管理系统 MVP。当前版本已支持 SQLite 持久化、Bearer Token 登录、RBAC 角色权限管理、动态菜单、中文企业后台，以及租户端小程序的合同、账单、报修和个人中心能力。

> 注意：管理后台和后端的真实项目目录是 `/Users/admin/Desktop/apartment `，目录名末尾有空格。命令中建议使用双引号包住路径。租户端微信小程序目前位于 `/Users/admin/Desktop/apartment/tenant-mini-program`。

## 项目结构

```text
.
├── backend/   # FastAPI REST API，SQLite 持久化数据、权限和租户端 API
└── frontend/  # Vue 3 + Vite 管理后台

/Users/admin/Desktop/apartment/tenant-mini-program
└── tenant-mini-program/  # 租户端微信小程序
```

## 默认演示账号

| 账号 | 密码 | 角色 |
| --- | --- | --- |
| `admin` | `admin123` | 系统管理员 |
| `manager` | `manager123` | 运营经理 |
| `leasing` | `leasing123` | 租务专员 |
| `maintenance` | `maintenance123` | 维修人员 |
| `finance` | `finance123` | 财务人员 |
| `viewer` | `viewer123` | 只读访客 |

开发/测试环境可通过 `APARTMENT_ENV=development APARTMENT_ENABLE_DEMO_SEED=true` 写入演示数据。SQLite 数据库默认位于 `backend/app.db`，该文件已被 `.gitignore` 忽略。生产环境默认不写入演示账号，需配置真实初始化账号。

租户端本地演示可使用 Tenant ID：`T-10001`。

## 后端启动

```bash
cd "/Users/admin/Desktop/apartment /backend"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
APARTMENT_ENV=development APARTMENT_ENABLE_DEMO_SEED=true uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

常用管理端接口：

- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/dashboard/summary`
- `GET /api/properties`
- `GET /api/tenants`
- `GET /api/contracts`
- `GET /api/maintenance-orders`
- `GET /api/finance/transactions`
- `GET /api/finance/reconciliation`
- `GET /api/permissions/catalog`
- `GET /api/permissions/roles`
- `POST /api/permissions/roles`
- `POST /api/permissions/resources`

常用租户端接口：

- `POST /api/tenant/auth/login`
- `POST /api/tenant/auth/bind`
- `GET /api/tenant/profile`
- `GET /api/tenant/contracts`
- `GET /api/tenant/bills`
- `POST /api/tenant/bills/{bill_id}/pay`
- `GET /api/tenant/repairs`
- `POST /api/tenant/repairs`
- `GET /api/tenant/home`

除登录、绑定和健康检查外，业务接口需要 `Authorization: Bearer <token>`。

## 前端启动

```bash
cd "/Users/admin/Desktop/apartment /frontend"
npm install
VITE_ENABLE_DEMO_ACCOUNTS=true npm run dev -- --host 127.0.0.1
```

前端通过 Vite proxy 将 `/api` 转发到 `http://127.0.0.1:8000`。

## 租户端微信小程序

小程序目录：

```bash
cd "/Users/admin/Desktop/apartment/tenant-mini-program"
```

使用微信开发者工具打开该目录即可预览。当前小程序页面包括：

- 登录：通过 Tenant ID 绑定或登录租户身份，本地演示可用 `T-10001`
- 首页：展示租户居住概览、快捷入口、最近合同、近期账单和报修动态
- 我的合同：展示当前合同详情和合同列表，合同列表已优化为卡片式 UI
- 我的账单：展示账单详情、状态和支付入口
- 报修服务：提交报修工单并查看工单进度
- 个人中心：展示当前绑定的租户身份和房间信息，支持退出登录

小程序默认调用后端 `http://127.0.0.1:8000` 的租户端 API。租户端认证使用微信登录 code + 租户账号绑定：

1. 小程序获取微信登录 code。
2. 调用 `/api/tenant/auth/login` 尝试登录。
3. 如果后端返回 `TENANT_NOT_BOUND`，小程序使用 Tenant ID 调用 `/api/tenant/auth/bind` 完成绑定。
4. 后端返回租户专用 Bearer Token，后续合同、账单、报修接口通过该 token 做租户级鉴权。

开发/测试环境默认启用微信 mock 登录，便于本地调试；非开发/测试环境禁止开启 mock 登录。

## 构建和测试

前端构建：

```bash
npm --prefix "/Users/admin/Desktop/apartment /frontend" run build
```

后端编译：

```bash
cd "/Users/admin/Desktop/apartment /backend"
source .venv/bin/activate
python3 -m compileall app
```

后端测试：

```bash
cd "/Users/admin/Desktop/apartment /backend"
source .venv/bin/activate
python3 -m pytest
```

微信小程序建议在微信开发者工具中执行编译预览，并手动验证：登录 → 首页 → 合同 → 账单 → 报修 → 个人中心。

## 配置项

后端支持通过环境变量覆盖：

- `APARTMENT_ENV`：运行环境，默认 `production`；非 `development/test` 时必须显式配置 `APARTMENT_JWT_SECRET`
- `APARTMENT_DB_PATH`：SQLite 数据库路径，默认 `backend/app.db`
- `APARTMENT_JWT_SECRET`：JWT 密钥，生产环境必须修改
- `APARTMENT_TOKEN_EXPIRE_MINUTES`：登录 token 有效期，默认 480 分钟
- `APARTMENT_ENABLE_DEMO_SEED`：是否写入默认演示账号，默认仅 `development/test` 环境开启，生产环境禁止开启
- `APARTMENT_ALLOW_DEMO_ROLE_HEADER`：是否允许旧版 `X-Demo-Role` 演示头，默认关闭，生产环境禁止开启
- `APARTMENT_WECHAT_APP_ID`：微信小程序 App ID
- `APARTMENT_WECHAT_APP_SECRET`：微信小程序 App Secret
- `APARTMENT_WECHAT_MOCK_LOGIN`：是否启用微信 mock 登录，默认仅 `development/test` 环境开启，生产环境禁止开启
- `VITE_ENABLE_DEMO_ACCOUNTS`：是否在前端展示演示账号和演示账号切换，默认关闭

安全说明：当前 MVP 管理后台前端将 Bearer Token 存入 `localStorage`，租户端小程序将租户 token 存入小程序本地存储，适合本地演示；生产部署应改为更严格的会话保护、密钥管理和微信真实登录校验方案。
