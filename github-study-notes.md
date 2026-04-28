# GitHub 顶级开源项目源码学习笔记

## 1. Flask 源码学习 (pallets/flask)

### 核心架构
Flask 源码的精髓在于其**设计极简但扩展性极强**。

**wsgi_app() 调用链：**
```
WSGI Server → wsgi_app() → RequestContext.push() → dispatch_request() → 返回响应
```

**关键类：**
- `Flask` — 主应用类，注册路由、配置、扩展
- `Request` — 封装 WSGI environ，提供 `request.args` / `request.json`
- `Response` — 响应对象，支持多种响应类型
- `Blueprint` — 路由分组，支持 `url_prefix`

**学到的最佳实践：**
1. **上下文管理**：`RequestContext` 和 `AppContext` 使用栈结构（`_request_ctx_stack`），支持嵌套请求
2. **装饰器模式**：`@app.route()` 本质是注册一个视图函数到 `url_map`
3. **延迟加载**：`@setupmethod` 确保在应用完全初始化前注册的扩展能正确绑定
4. **信号机制**：`blinker` 实现的信号（`request_started`, `request_finished`）用于解耦

### 应用在工厂系统
```python
# 仿Flask上下文，设计BatchContext追踪当前批次操作
from contextvars import ContextVar

current_batch = ContextVar('current_batch')

def set_current_batch(batch):
    current_batch.set(batch)

def log_operation(operation):
    batch = current_batch.get()
    # 自动记录操作到当前批次
```

---

## 2. vue-vben-admin 源码架构

### 目录结构精析
```
src/
├── api/          # API 请求层，按模块拆分
├── assets/       # 静态资源
├── components/   # 通用组件（增强表格/表单/流程图）
│   ├── basic/    # 基础组件（按钮、输入框等封装）
│   └── business/ # 业务组件
├── composables/  # 组合式函数（hooks）
│   ├── usePermission.ts  # 权限 hook
│   └── useTable.ts       # 表格 hook
├── core/         # 核心逻辑
│   └── permission.ts     # 权限校验引擎
├── directives/   # 自定义指令
├── layouts/      # 布局组件
├── locales/      # 国际化
├── router/       # 路由配置 + 权限路由
│   └── guard/    # 路由守卫（权限检查）
├── store/        # Pinia 状态
├── utils/        # 工具函数
└── views/        # 页面组件
```

### 权限系统设计（RBAC + 动态路由）
```
用户登录 → 获取角色/权限码 → 动态生成路由表 → 路由守卫拦截 → 渲染菜单
```
- `permission.ts` 核心：根据权限码 `filterAsyncRoutes()` 过滤路由
- 按钮级权限：自定义指令 `v-auth="['batch:delete']"`
- 角色层级：`admin > operator > inspector`

### 学到的最佳实践
1. **Composable 分离**：`useTable`、`useForm` 将表格和表单逻辑封装为 hook，组件只负责渲染
2. **请求封装**：`axios` 拦截器统一处理 token 注入、错误提示、超时重试
3. **路由拆分**：按功能模块拆分路由配置，`routes/modules/` 下每个模块独立文件
4. **TypeScript 严格模式**：所有 API 响应有类型定义，`ApiResult<T>` 泛型封装

---

## 3. Element Plus 组件库源码分析

### 组件设计模式
每个组件一个目录，例如 `packages/components/button/`：
```
button/
├── src/
│   ├── button.ts       # 组件逻辑 (defineComponent)
│   ├── button.vue      # 模板
│   └── constants.ts    # 常量
├── style/              # 样式（CSS变量驱动）
└── test/               # 单元测试
```

### 学到了什么
1. **Props 设计**：所有 Props 用 TypeScript 接口定义，默认值清晰
2. **provide/inject 透传**：`ElForm` → `ElFormItem` 通过 provide 传递校验规则
3. **CSS 变量主题**：使用 `--el-color-primary` 等CSS变量，主题切换只需修改变量
4. **按需加载**：每个组件独立导出，`unplugin-vue-components` 自动按需引入

### 应用到工厂系统
```typescript
// 仿Elements Plus 设计 BatchForm 组件
// 传入 batch 对象，自动校验必填字段
interface BatchFormProps {
  batch?: Batch
  mode: 'create' | 'edit' | 'view'
  readonly?: boolean
}
```

---

## 4. Apache Superset 架构学习

### 整体架构
```
Web 层 (React) → API 层 (Flask-RESTx) → 逻辑层 → 数据库
                                    ↓
                              Celery (异步)
                                    ↓
                              Redis (缓存)
```

### 学到的最佳实践（Python大型项目）
1. **配置分层**：
   - `config.py` — 默认配置
   - `config.py` 中的 `from_envvar` — 通过环境变量覆盖
   - `SECRET_KEY` 等敏感信息永不硬编码
2. **自定义异常体系**：
   ```python
   class SupersetException(Exception): pass
   class DatabaseNotFound(SupersetException): pass
   class QueryTimeout(SupersetException): pass
   ```
3. **统一 JSON API**：
   ```python
   @app.errorhandler(SupersetException)
   def handle_superset_error(ex):
       return jsonify({'error': str(ex), 'status': 'error'}), 400
   ```
4. **数据库迁移**：Alembic + 自动迁移脚本
5. **国际化**：`Babel` + `.po` 文件翻译

---

## 5. GitHub Actions CI/CD 最佳实践

### 典型 Python 项目 CI 流水线（参考 Superset/Airflow）

```yaml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install flake8 mypy
      - run: flake8 src/ tests/
      - run: mypy src/

  test:
    needs: lint
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - run: pip install -e ".[dev]"
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v3

  docker:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: docker build -t app .
      - run: docker tag app registry.example.com/app:${{ github.sha }}
      - run: docker push registry.example.com/app:${{ github.sha }}
```

### 学到的最佳实践
1. **分阶段**：lint → test → build → deploy，每阶段依赖上一阶段
2. **服务容器**：用 `services` 启动 PostgreSQL/Redis 用于集成测试
3. **矩阵测试**：多 Python 版本测试 `strategy.matrix.python-version`
4. **缓存依赖**：`actions/cache` 缓存 `pip` 和 `npm` 依赖加速构建

---

## 6. Vue3 组合式 API 最佳实践（来自顶级项目）

### 通用 Hooks 设计模式

```typescript
// 1. useRequest — 通用请求 hook
export function useRequest<T>(api: () => Promise<T>) {
  const data = ref<T | null>(null)
  const loading = ref(false)
  const error = ref<Error | null>(null)

  async function execute() {
    loading.value = true
    error.value = null
    try {
      data.value = await api()
    } catch (e) {
      error.value = e as Error
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, execute }
}

// 2. useWebSocket — WebSocket 连接 hook
export function useWebSocket(url: string) {
  const connected = ref(false)
  const lastMessage = ref<any>(null)
  let ws: WebSocket | null = null

  function connect() {
    ws = new WebSocket(url)
    ws.onopen = () => { connected.value = true }
    ws.onmessage = (e) => { lastMessage.value = JSON.parse(e.data) }
    ws.onclose = () => { connected.value = false }
  }

  onUnmounted(() => ws?.close())

  return { connected, lastMessage, connect }
}
```

---

## 7. 总结：工厂系统应该借鉴的代码模式

| 模式 | 来源项目 | 应用到工厂系统 |
|------|---------|--------------|
| 上下文管理器 | Flask | BatchContext 追踪批次操作 |
| 动态路由 + 权限 | vue-vben-admin | 按角色动态显示车间页面 |
| 自定义异常体系 | Superset | BatchError、DeviceError 等 |
| 按需组件加载 | Element Plus | 大屏图表懒加载 |
| Composable Hooks | Vben | useBatch、useDevice hook |
| 配置分层 | Superset | 开发/测试/生产配置 |
| 服务容器 CI | GitHub Actions | 测试数据库隔离 |
| CSS 变量主题 | Element Plus | 大屏主题切换 |
