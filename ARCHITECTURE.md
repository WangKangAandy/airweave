# Airweave 项目架构详解

## 一、项目模块划分

Airweave 是一个**单体仓库**，包含 4 个主要业务模块：

### 1. **Backend** (`backend/`)
- **技术栈**: Python 3.13, FastAPI, SQLAlchemy Async
- **职责**: 核心业务逻辑、API 服务、数据同步协调
- **关键组件**:
  - `api/v1/endpoints/` - RESTful API 路由
  - `domains/` - 领域驱动设计（业务逻辑）
  - `platform/sources/` - 50+ 数据源连接器
  - `platform/destinations/` - 向量数据库适配器

### 2. **Frontend** (`frontend/`)
- **技术栈**: React 18, TypeScript, Vite, ShadCN UI
- **职责**: 用户界面、连接管理、搜索交互
- **关键组件**:
  - `components/` - UI 组件库
  - `pages/` - 页面路由
  - `lib/stores/` - Zustand 状态管理

### 3. **MCP Server** (`mcp/`)
- **技术栈**: Node.js, TypeScript
- **职责**: 模型上下文协议服务器，为 AI 助手提供集成
- **部署模式**:
  - 本地模式 (stdio)
  - 托管模式 (HTTP)

### 4. **Support Tools**
- **Monke** (`monke/`) - E2E 测试框架
- **Fern** (`fern/`) - API 文档生成
- **Vespa** (`vespa/`) - 向量搜索引擎配置

---

## 二、容器协同架构（11 个容器）

### 🗃️ **数据层**（3 个容器）
```yaml
postgres          # PostgreSQL - 元数据存储（用户、连接、配置）
redis             # Redis - 缓存 + 消息队列（pub/sub）
vespa             # Vespa - 向量数据库（搜索索引）
```

### 🚀 **应用层**（3 个容器）
```yaml
backend           # FastAPI 服务 - REST API + 业务逻辑
frontend          # React 应用 - 用户界面
connect           # Connect widget - 嵌入式组件（可选）
```

### ⚙️ **任务编排层**（3 个容器）
```yaml
temporal          # Temporal 服务器 - 工作流引擎
temporal-worker    # Worker 进程 - 执行数据同步任务
temporal-ui       # Temporal UI - 工作流监控界面
```

### 🛠️ **辅助服务**（2 个容器）
```yaml
text2vec-transformers  # 本地嵌入模型服务
svix                 # Webhook 管理服务
```

---

## 三、模块协同流程

### 数据流：Sources → Embeddings → Vector DB → Search

```
┌─────────────┐
│  Frontend   │ ◄─────┐
│  (React)    │        │
└──────┬──────┘        │
       │ HTTP API        │
       ▼                │
┌─────────────┐         │
│   Backend   │         │
│  (FastAPI)  │────────┘
└──────┬──────┘
       │
       ├──────────┐
       │          │
       ▼          ▼
┌─────────────┐  ┌─────────────┐
│  Temporal   │  │  Postgres   │
│   Worker    │  │  (Metadata) │
└──────┬──────┘  └─────────────┘
       │
       ├─ Sources (50+ connectors)
       ├─ Entities (数据提取)
       ├─ Embeddings (向量化)
       └─ Vespa (向量存储)

实时通知: Redis Pub/Sub
进度追踪: Temporal Workflows
```

### 关键协同机制

1. **API 通信**: Frontend → Backend (REST API)
2. **任务调度**: Backend → Temporal (启动同步)
3. **任务执行工作流**: Temporal Worker → Sources → Embeddings → Vespa
4. **实时通知**: Worker → Redis → Frontend (SSE/WebSocket)
5. **状态持久化**: Worker → Postgres (同步状态)

---

## 四、维护难度分析

### ⚠️ **挑战点**

1. **运维复杂度高**
   - 11 个容器需要协调启动
   - 服务依赖关系复杂
   - 配置管理分散

2. **调试困难**
   - 分布式系统调试
   - 日志分散在多个容器
   - 性能瓶颈定位难

3. **资源消耗大**
   - 每个服务独立运行
   - 开发环境需要较多内存
   - 本地开发要求高配置机器

4. **技术栈多样**
   - Python、Node.js、数据库、搜索引擎
   - 每个领域需要不同技能栈

### ✅ **优势**

1. **模块化设计**
   - 各组件独立部署
   - 单一职责原则
   - 易于扩展和维护

2. **容器化部署**
   - 一键启动所有服务
   - 环境一致性保证
   - 开发/生产环境对等

3. **完善的监控**
   - 健康检查机制
   - 自动重启策略
   - Temporal UI 可视化

4. **渐进式开发**
   - `./start.sh --skip-frontend` - 只启动后端
   - 可独立测试各模块
   - 支持微服务式开发

---

## 五、开发建议

### 🔧 **开发时简化策略**

```bash
# 1. 只启动核心服务（快速开发）
./start.sh --skip-frontend

# 2. 前端独立开发（热重载）
cd frontend && npm run dev

# 3. 只测试特定功能
docker-compose up backend postgres redis
```

### 📊 **监控和调试**

```bash
# 查看服务状态
docker-compose ps

# 查看特定服务日志
docker logs airweave-backend --tail 100

# 进入容器调试
docker exec -it airweave-backend bash

# Temporal 工作流监控
# 访问: http://localhost:8088
```

### 🚀 **优化建议**

1. **开发环境优化**
   - 使用开发配置减少资源消耗
   - 启用代码热重载
   - 使用轻量级数据库

2. **生产环境优化**
   - Kubernetes 编排替代 Docker Compose
   - 集中式日志收集
   - 集中式监控（Prometheus + Grafana）

3. **团队协作优化**
   - 明确模块边界和接口
   - API 版本控制
   - 完善的文档和测试

---

## 总结

Airweave 的**11 个容器架构**确实复杂，但这是为了实现以下功能：

- **50+ 数据源支持**需要独立连接器
- **向量搜索**需要专用搜索引擎
- **异步任务编排**需要 Temporal
- **实时通信**需要 Redis
- **Webhook 管理**需要 Svix

**对于开发维护**：
- ❌ 初期学习曲线陡峭
- ✅ 一旦熟悉，模块化设计反而更易维护
- ✅ 容器化部署减少了环境配置问题
- ✅ 提供了良好的扩展性基础

建议从简化配置开始，逐步熟悉各模块功能，再进行深度开发。
