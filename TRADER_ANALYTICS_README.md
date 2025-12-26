# Trader Analytics System

完整的交易者分析查询系统，包含后端API服务和前端可视化界面。

## 功能特性

### 后端 API (Flask)
- 交易者列表查询（支持分页、评级筛选）
- 交易者详细信息
- 历史交易记录查询
- 历史数据图表（收益率、收益额、资产）
- 统计信息汇总

### 前端界面 (React + Vite)
- 交易者列表页面
  - 评级筛选 (S/A/B/C/D/F)
  - 地址搜索
  - 多维度指标展示
  - 点击查看详情

- 交易者详情页面
  - 概览信息（总交易数、胜率、总盈亏、资产等）
  - 交互式图表（Tabs）
    - 收益率 (ROI) 折线图
    - 收益额 (PnL) 折线图
    - 资产 (Equity) 折线图
  - 历史交易记录表格

## 安装和运行

### 1. 安装后端依赖

```bash
pip install -r requirements-api.txt
```

### 2. 安装前端依赖

```bash
cd web
pnpm install
```

### 3. 配置环境变量

创建 `web/.env` 文件（参考 `web/.env.example`）:

```env
VITE_API_URL=http://localhost:5000/api
```

### 4. 启动后端 API 服务

```bash
# 在项目根目录
python api_server.py
```

API 服务将在 `http://localhost:5000` 启动

### 5. 启动前端开发服务器

```bash
cd web
pnpm dev
```

前端将在 `http://localhost:5173` 启动

## API 端点

### 交易者相关
- `GET /api/traders` - 获取交易者列表
  - 参数: `limit`, `min_rating`, `offset`

- `GET /api/traders/<address>` - 获取交易者详情

- `GET /api/traders/<address>/fills` - 获取历史交易记录
  - 参数: `limit`, `coin`

- `GET /api/traders/<address>/history` - 获取历史图表数据
  - 参数: `limit`

- `GET /api/traders/rating/<rating>` - 按评级筛选交易者

### 统计相关
- `GET /api/stats` - 获取数据库统计信息
- `GET /api/sessions` - 获取筛选会话列表
- `GET /api/sessions/<session_id>/traders` - 获取会话的交易者

### 健康检查
- `GET /health` - API 健康检查

## 技术栈

### 后端
- Flask 3.0.0
- Flask-CORS 4.0.0
- SQLite (通过 `screener/database.py`)

### 前端
- React 18.3.1
- Vite 6.0.11
- HeroUI (UI组件库)
- Recharts (图表库)
- Axios (HTTP客户端)
- React Router (路由)
- TailwindCSS (样式)

## 数据库

系统使用 SQLite 数据库，表结构包括：

- `trader_metrics` - 交易者指标数据
- `trader_fills` - 历史交易记录
- `screening_sessions` - 筛选会话
- `session_traders` - 会话-交易者关联表

数据库位置: `data/traders.db` (默认)

## 开发说明

### 添加新的 API 端点
在 `api_server.py` 中添加新的路由处理函数。

### 添加新的前端页面
1. 在 `web/src/pages/` 创建新页面组件
2. 在 `web/src/App.tsx` 中添加路由
3. 在 `web/src/config/site.ts` 中添加导航链接（可选）

### 修改图表样式
在 `web/src/pages/trader-detail.tsx` 中修改 Recharts 组件的配置。

## 注意事项

1. 确保数据库中已有交易者数据（通过 `screen_traders.py` 导入）
2. API 服务默认允许跨域请求（CORS）
3. 前端开发服务器默认端口 5173，API 服务器默认端口 5000
4. 生产环境部署时需要配置适当的 CORS 策略

## 截图

访问 `http://localhost:5173/traders` 查看交易者列表页面
点击任意交易者查看详情页面，包含图表和历史交易记录

## 许可

与主项目保持一致
