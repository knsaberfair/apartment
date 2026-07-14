# 公寓管理系统

基于 **Vue 3 + Vite + TypeScript + Tailwind CSS** 和 **Python + FastAPI** 的公寓管理系统 MVP。UI 风格参考 Stitch 项目 `Apartment Management System`：深色侧边栏、卡片化数据看板、紧凑表格、状态标签和中文企业后台体验。

## 项目结构

```text
.
├── backend/   # FastAPI REST API，当前使用内存 mock 数据
└── frontend/  # Vue 3 + Vite 管理后台
```

## 后端启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

常用接口：

- `GET /api/dashboard/summary`
- `GET /api/properties`
- `GET /api/tenants`
- `GET /api/contracts`
- `GET /api/maintenance-orders`
- `GET /api/finance/transactions`
- `GET /api/finance/reconciliation`

## 前端启动

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

前端通过 Vite proxy 将 `/api` 转发到 `http://127.0.0.1:8000`。

## 构建检查

```bash
cd frontend
npm run build
```

```bash
cd backend
python -m compileall app
```
