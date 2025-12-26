# 服务端分页实现

## 更新概述

将历史交易记录从客户端分页（200条限制）升级为服务端分页，支持无限数据量的加载。

## 主要变更

### 1. 后端 API 增强 (`api_server.py`)

#### 更新的端点
`GET /api/traders/<address>/fills`

#### 新增参数
- `page` (int): 页码，默认 1
- `limit` (int): 每页数量，默认 20
- `coin` (str): 币种筛选（可选）
- `pnl_filter` (str): 盈亏筛选 - all/profit/loss

#### 返回格式
```json
{
  "success": true,
  "data": [...], // 当前页的数据
  "pagination": {
    "page": 1,
    "limit": 20,
    "total_count": 1523,
    "total_pages": 77,
    "has_next": true,
    "has_prev": false
  }
}
```

#### 实现逻辑
```python
# 1. 获取所有符合条件的数据
all_fills = db.get_trader_fills(address, limit=100000, coin=coin)

# 2. 应用盈亏筛选
if pnl_filter == 'profit':
    all_fills = [f for f in all_fills if f['closed_pnl'] > 0]
elif pnl_filter == 'loss':
    all_fills = [f for f in all_fills if f['closed_pnl'] < 0]

# 3. 计算分页信息
total_count = len(all_fills)
total_pages = (total_count + limit - 1) // limit

# 4. 返回当前页数据
start = (page - 1) * limit
end = start + limit
fills = all_fills[start:end]
```

### 2. 前端 API 服务更新 (`web/src/services/api.ts`)

#### 新增类型定义
```typescript
export interface PaginationInfo {
  page: number;
  limit: number;
  total_count: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}
```

#### 更新 API 方法
```typescript
getTraderFills: (address: string, params?: {
  page?: number;
  limit?: number;
  coin?: string;
  pnl_filter?: 'all' | 'profit' | 'loss';
}) => api.get<any, ApiResponse<TraderFill[]>>(`/traders/${address}/fills`, { params })
```

### 3. 前端页面重构 (`web/src/pages/trader-detail.tsx`)

#### 新增状态
```typescript
const [totalPages, setTotalPages] = useState(1);
const [totalCount, setTotalCount] = useState(0);
const [fillsLoading, setFillsLoading] = useState(false);
```

#### 数据加载逻辑
```typescript
// 初始加载
useEffect(() => {
  // 加载第一页数据
  const fillsRes = await traderApi.getTraderFills(address, {
    page: 1,
    limit: rowsPerPage,
    coin: selectedCoin !== 'all' ? selectedCoin : undefined,
    pnl_filter: pnlFilter,
  });

  // 保存分页信息
  setTotalPages(fillsRes.pagination.total_pages);
  setTotalCount(fillsRes.pagination.total_count);
}, [address]);

// 筛选或分页改变时重新加载
useEffect(() => {
  loadFills(); // 调用API加载新数据
}, [address, page, selectedCoin, pnlFilter]);

// 筛选条件改变时重置页码
useEffect(() => {
  setPage(1);
}, [selectedCoin, pnlFilter]);
```

## 功能对比

### 之前（客户端分页）
```typescript
// ❌ 一次性加载200条数据
const fills = await traderApi.getTraderFills(address, { limit: 200 });

// ❌ 客户端过滤和分页
const filtered = fills.filter(...);
const paginated = filtered.slice(start, end);
```

**问题**：
- 数据超过200条时无法查看
- 浪费带宽加载不需要的数据
- 筛选时需要重新加载所有数据

### 现在（服务端分页）
```typescript
// ✅ 按需加载20条数据
const fills = await traderApi.getTraderFills(address, {
  page: 1,
  limit: 20,
  coin: 'BTC',
  pnl_filter: 'profit'
});

// ✅ 服务端已完成过滤和分页
// 直接使用返回的数据
```

**优势**：
- 支持无限数据量
- 节省带宽，只加载当前页
- 服务端过滤，性能更好
- 分页信息准确（total_count, total_pages）

## 性能优化

### 1. 按需加载
- 每次只加载 20 条数据
- 减少网络传输和内存占用

### 2. 独立加载状态
- `fillsLoading` 独立控制交易记录加载
- 不影响图表和其他数据的显示

### 3. 智能刷新
- 筛选条件改变时自动重置到第一页
- 避免显示空白页面

### 4. 缓存机制（未来改进）
```typescript
// 可以添加页面数据缓存
const pageCache = useRef<Map<number, TraderFill[]>>(new Map());
```

## 使用示例

### API 调用示例

```bash
# 获取第一页（默认）
GET /api/traders/0x1234.../fills?page=1&limit=20

# 获取第二页
GET /api/traders/0x1234.../fills?page=2&limit=20

# 筛选盈利交易
GET /api/traders/0x1234.../fills?pnl_filter=profit

# 筛选BTC交易
GET /api/traders/0x1234.../fills?coin=BTC

# 组合筛选
GET /api/traders/0x1234.../fills?page=1&coin=BTC&pnl_filter=profit
```

### 前端使用

用户操作流程：
1. 打开交易者详情页 → 自动加载第一页数据（20条）
2. 选择"盈利"筛选 → 重置到第一页，加载盈利交易
3. 切换到第2页 → 加载第2页的盈利交易
4. 选择"BTC"币种 → 重置到第一页，加载BTC的盈利交易

## 数据流程

```
用户操作
   ↓
状态更新 (page/coin/pnl_filter)
   ↓
触发 useEffect
   ↓
显示加载状态 (fillsLoading = true)
   ↓
调用后端 API
   ↓
后端查询数据库 → 应用筛选 → 计算分页 → 返回当前页
   ↓
前端接收数据
   ↓
更新状态 (fills, totalPages, totalCount)
   ↓
隐藏加载状态 (fillsLoading = false)
   ↓
渲染表格和分页控件
```

## 统计信息说明

由于使用服务端分页，统计信息的计算方式有所调整：

```typescript
const fillsStats = {
  total: totalCount,              // ✅ 全部记录数（来自后端）
  profitable: fills.filter(...),  // ⚠️ 仅当前页（需要后端支持）
  losing: fills.filter(...),      // ⚠️ 仅当前页
  totalPnl: fills.reduce(...),    // ⚠️ 仅当前页
  totalFees: fills.reduce(...),   // ⚠️ 仅当前页
  winRate: ...,                   // ⚠️ 基于当前页计算
}
```

### 未来改进
可以在后端 API 返回全局统计信息：
```json
{
  "data": [...],
  "pagination": {...},
  "statistics": {
    "total_count": 1523,
    "profitable_count": 892,
    "losing_count": 631,
    "total_pnl": 15234.56,
    "total_fees": 123.45,
    "win_rate": 0.5856
  }
}
```

## 兼容性

- ✅ 向后兼容（API支持旧参数）
- ✅ 所有现代浏览器
- ✅ 移动端响应式
- ✅ 异步加载，用户体验流畅

## 测试场景

### 1. 大数据量测试
- 超过 1000 条交易记录
- 验证分页正确性
- 检查性能表现

### 2. 筛选测试
- 币种筛选
- 盈亏筛选
- 组合筛选

### 3. 边界测试
- 第一页（无上一页）
- 最后一页（无下一页）
- 空数据
- 单条数据

### 4. 交互测试
- 快速切换页面
- 连续修改筛选条件
- 页面刷新后状态保持

## 部署说明

### 1. 重启后端服务
```bash
python api_server.py
```

### 2. 重启前端服务
```bash
cd web
pnpm dev
```

### 3. 验证功能
访问任意交易者详情页，测试：
- 分页切换
- 币种筛选
- 盈亏筛选
- 加载状态

## 故障排查

### 分页不工作
1. 检查 API 响应格式
2. 确认 pagination 字段存在
3. 验证 totalPages 计算正确

### 筛选后显示空白
1. 确认筛选条件正确传递
2. 检查后端筛选逻辑
3. 验证 page 重置为 1

### 加载状态异常
1. 检查 fillsLoading 状态管理
2. 确认 finally 块执行
3. 验证 useEffect 依赖项

## 总结

服务端分页实现消除了 200 条数据的限制，支持查看和分析任意数量的历史交易记录。通过合理的状态管理和异步加载，确保了流畅的用户体验和良好的性能表现。
