# Airweave 故障排查 FAQ

## 🚀 自动 IP 配置说明

Airweave 现已实现自动 IP 管理，无需手动配置 IP 地址：

### 本地开发
- **访问方式**: http://localhost:8080
- **API 配置**: 自动使用 http://localhost:8001
- **配置方法**: 无需任何配置，开箱即用

### 远程访问
- **访问方式**: http://your-server-ip:8080
- **API 配置**: 前端会根据访问地址自动适配
- **配置方法**: 系统自动检测并配置最佳 API 地址

### 配置优先级
1. 环境变量 `FRONTEND_API_URL` (最高优先级)
2. 浏览器地址自动检测
3. 默认值 `http://localhost:8001`

### 技术实现
- 前端配置支持多层级配置机制
- Docker 移除了硬编码 IP 地址
- 支持不同网络环境的零配置部署

---

## Q1: 浏览器无法加载 collections，报错 "An error occurred: Failed to fetch"

### 问题症状
- 前端页面能正常加载
- Collections 页面显示错误："An error occurred: Failed to fetch"
- 浏览器开发者工具 Network 标签显示 API 请求失败

### 系统状态检查清单

#### 1. 容器状态检查
```bash
# 检查所有容器是否健康运行
docker ps --filter "name=airweave" --format "table {{.Names}}\t{{.Status}}"

# 预期输出: 所有容器显示 "Up X minutes (healthy)"
```

#### 2. 前端配置检查
```bash
# 检查前端容器的 API_URL 配置
docker logs airweave-frontend --tail 20 | grep "API_URL"
# 预期输出: Runtime config injected successfully. API_URL set to: http://localhost:8001

# 检查生成的 config.js 文件
docker exec airweave-frontend cat /app/dist/config.js
# 预期: API_URL: "http://localhost:8001"
```

#### 3. 后端健康检查
```bash
# 检查后端健康状态
curl http://localhost:8001/health/ready
# 预期输出: {"status":"healthy"} 或类似健康响应
```

#### 4. CORS 配置检查
```bash
# 测试 OPTIONS 预检请求
curl -X OPTIONS http://localhost:8001/api/v1/collections \
  -H "Origin: http://localhost:8080" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization,Content-Type" \
  -v 2>&1 | grep "< HTTP"
# 预期输出: < HTTP/1.1 200 OK
```

#### 5. 后端日志检查
```bash
# 查看后端最近的请求日志
docker logs airweave-backend --tail 50 | grep -E "GET|POST|OPTIONS|collections"

# 查看是否有 CORS 相关错误
docker logs airweave-backend --tail 50 | grep -i "cors|origin"
```

#### 6. 前端日志检查
```bash
# 查看前端最近的请求
docker logs airweave-frontend --tail 30

# 查看是否有配置或错误信息
docker logs airweave-frontend --tail 30 | grep -E "API_URL|error|Error"
```

### 常见问题及解决方案

#### 问题 1: API_URL 配置错误
**症状**: 浏览器尝试向错误的地址发起请求
**检查**: 浏览器开发者工具 Network 标签中的请求 URL
**解决**: 修改 `docker/docker-compose.yml` 中的前端 `API_URL` 环境变量

#### 问题 2: CORS 配置错误
**症状**: OPTIONS 请求返回 403 或 500
**检查**: `curl` 测试 OPTIONS 请求
**解决**: 检查 `backend/airweave/api/middleware.py` 中的 CORS 配置

#### 问题 3: 后端服务异常
**症状**: API 请求返回 500 错误或超时
**检查**: 后端日志中的异常堆栈
**解决**: 检查数据库连接、依赖服务等

#### 问题 4: 认证问题
**症状**: API 请求返回 401 或 403
**检查**: 浏览器 Network 标签中的响应头
**解决**: 检查 `ENABLE_AUTH` 配置和认证令牌

### 调试步骤

1. **打开浏览器开发者工具** (F12)
   - 切换到 Network 标签
   - 刷新页面
   - 找到失败的 API 请求（红色）

2. **检查请求详情**
   - 点击失败的请求
   - 查看 Headers 标签：确认请求 URL、Method、Headers
   - 查看 Response 标签：确认状态码和响应内容
   - 查看 Console 标签：查看 JavaScript 错误信息

3. **对比服务器日志**
   - 执行上面的系统状态检查命令
   - 在后端日志中查找对应的请求
   - 在前端日志中查找可能的错误

4. **针对性测试**
   - 使用 `curl` 命令模拟浏览器请求
   - 逐步排除网络、CORS、认证等问题

### 相关日志位置

- **前端日志**: `docker logs airweave-frontend`
- **后端日志**: `docker logs airweave-backend`
- **数据库日志**: `docker logs airweave-db`
- **Redis日志**: `docker logs airweave-redis`
- **浏览器日志**: 浏览器开发者工具 Console 和 Network 标签

### 修复记录

#### 修复 1: 前端 API_URL 配置错误
**日期**: 2026-04-10
**问题**: 前端 API_URL 配置为 `http://localhost:8001`，远程访问时浏览器尝试向客户端 localhost 发起请求
**解决**: 系统已升级为自动 IP 管理，默认使用 `http://localhost:8001` 进行本地开发。如需远程访问，可以通过前端动态检测或配置环境变量
**状态**: 已通过无感配置解决

#### 修复 2: 浏览器缓存导致无法加载 collections
**日期**: 2026-04-10
**问题**: 前端配置正确，但浏览器使用缓存的旧版本 JavaScript 文件，导致 API 请求失败
**症状**: 浏览器显示 "An error occurred: Failed to fetch"
**检查方法**:
```bash
# 1. 检查前端日志中的缓存状态
docker logs airweave-frontend --tail 10 | grep -E "GET|304"

# 2. 检查浏览器 Network 标签中的资源加载状态
# 查看 assets/index-*.js 是否返回 304 (缓存)

# 3. 强制清除浏览器缓存
# Windows/Linux: Ctrl + Shift + R
# Mac: Cmd + Shift + R
```
**解决**: 强制清除浏览器缓存，确保加载最新的配置文件
**状态**: 需要用户验证

### 关键技术要点

#### 1. API 端点路径
- **正确**: `/collections`、`/organizations` 等
- **错误**: `/api/v1/collections` (返回 404)
- **检查方法**: `curl http://localhost:8001/openapi.json | grep -o '"/[^"]*"'`

#### 2. 前端配置优先级
1. `window.ENV.API_URL` (容器启动时生成)
2. `import.meta.env.VITE_API_URL` (构建时设置)
3. 默认值: `http://localhost:8001`

#### 3. 浏览器缓存行为
- HTTP 304: 使用缓存版本
- HTTP 200: 重新加载
- 强制刷新可以绕过缓存

## Q2: 创建 Source Connection 失败，报错 "Namespace default has no mapping defined for search attribute SyncId"

### 问题症状
- 在创建 Source Connection 时失败
- 错误信息：`{"detail":"Internal Server Error: RPCError: Namespace default has no mapping defined for search attribute SyncId"}`
- 前端显示连接创建失败

### 系统状态检查清单

#### 1. Temporal 服务状态检查
```bash
# 检查 Temporal 服务是否健康运行
docker ps --filter "name=airweave-temporal" --format "table {{.Names}}\t{{.Status}}"

# 预期输出: airweave-temporal 显示 "healthy"
```

#### 2. Temporal 搜索属性配置检查
```bash
# 检查 Temporal 搜索属性列表
docker exec airweave-temporal tctl --address temporal:7233 --namespace default search-attribute list

# 预期输出: 应该包含 SyncId 搜索属性
```

#### 3. Temporal-init 容器状态检查
```bash
# 检查 temporal-init 容器是否成功运行并注册了搜索属性
docker logs airweave-temporal-init

# 预期输出: 应该看到 "SyncId search attribute registered"
```

#### 4. 后端日志检查
```bash
# 查看后端最近的错误日志
docker logs airweave-backend --tail 100 | grep -E "SyncId|search.attribute|RPCError"

# 查找 Temporal 相关的错误
docker logs airweave-backend --tail 100 | grep -i "temporal"
```

#### 5. Temporal UI 检查
```bash
# 访问 Temporal UI 检查工作流状态
# http://localhost:8088/namespace/default/workflows

# 检查是否有创建的同步工作流
```

### 调试步骤

1. **检查 temporal-init 容器日志**
   ```bash
   docker logs airweave-temporal-init
   ```
   预期应该看到：`SyncId search attribute registered`
   如果看到错误或缺少此消息，说明搜索属性未正确注册

2. **手动注册搜索Attribute**
   ```bash
   docker exec airweave-temporal tctl --address temporal:7233 --namespace default search-attribute create \
     --name SyncId --type Keyword || true
   ```

3. **验证搜索属性注册**
   ```bash
   docker exec airweave-temporal tctl --address temporal:7233 --namespace default search-attribute list
   ```
   预期输出应包含：`SyncId (Keyword)`

4. **重试创建 Source Connection**
   - 刷新前端页面
   - 重新尝试创建 Source Connection

5. **检查后端完整日志**
   ```bash
   docker logs airweave-backend --tail 200 | grep -A 10 -B 10 "SyncId"
   ```

### 常见问题及解决方案

#### 问题 1: temporal-init 容器未成功注册搜索属性
**症状**: temporal-init 日志中没有 "SyncId search attribute registered"
**检查**: `docker logs airweave-temporal-init`
**解决**: 手动注册搜索属性（见步骤2）

#### 问题 2: Temporal 服务重启导致搜索属性丢失
**症状**: 之前工作正常，重启后出现此错误
**检查**: `docker restart airweave-temporal` 后搜索属性丢失
**解决**: Temporal 搜索属性需要持久化配置或重新初始化

#### 问题 3: 容器启动顺序问题
**症状**: 后端在 Temporal 完全初始化前启动
**检查**: docker-compose 中的 depends_on 配置
**解决**: 修改容器启动顺序或添加健康检查依赖

### 相关日志位置

- **后端日志**: `docker logs airweave-backend`
- **Temporal init 日志**: `docker logs airweave-temporal-init`
- **Temporal 日志**: `docker logs airweave-temporal`
- **浏览器日志**: 浏览器开发者工具 Console 和 Network 标签

### 修复记录

#### 修复 1: 手动注册 Temporal 搜索属性
**日期**: 2026-04-10
**问题**: temporal-init 容器未成功注册 SyncId 搜索属性，导致创建 Source Connection 失败
**症状**: `{"detail":"Internal Server Error: RPCError: Namespace default has no mapping defined for search attribute SyncId"}`
**根原因**: temporal-init 容器使用错误的连接地址（主机名而非 Docker 内部 IP），Alpine 容器无法解析 Docker 内部主机名
**解决**: 手动执行命令注册搜索属性
**状态**: ✅ 已验证解决

**修复命令**:
```bash
docker exec airweave-temporal /usr/local/bin/temporal operator search-attribute create --name SyncId --type Keyword --namespace default --address temporal:7233
```

**验证方法**:
```bash
docker exec airweave-temporal /usr/local/bin/temporal operator search-attribute list --namespace default --address temporal:7233
# 应该看到 SyncId 在列表中
```

**技术分析**:
- temporal-init 容器尝试使用主机名连接 Temporal 服务
- 使用 Docker 服务名 `temporal` 代替硬编码 IP
- Docker 内部 DNS 会自动解析服务名到正确的容器 IP
- 这种方式更灵活，适用于不同的 Docker 网络配置

## Q3: GitHub Source 同步失败，报错 tiktoken 编码下载失败

### 问题症状
- GitHub source 可以成功创建
- 同步状态显示 "failed"
- 错误日志：`[ChunkEmbedProcessor] CodeChunker failed: Failed to initialize CodeChunker: Failed to load tiktoken encoding 'cl100k_base': HTTPSConnectionPool(host='openaipublic.blob.core.windows.net', port=443): Max retries exceeded`
- DNS 解析失败：`Name or service not known`

### 系统状态检查清单

#### 1. 网络连接检查
```bash
# 检查容器是否能访问外网
docker exec airweave-backend ping -c 3 8.8.8.8

# 检查 DNS 解析
docker exec airweave-backend nslookup openaipublic.blob.core.windows.net

# 检查是否能访问 OpenAI 的 tiktoken 文件
docker exec airweave-backend curl -I https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
```

#### 2. tiktoken 库状态检查
```bash
# 检查 tiktoken 是否已安装
docker exec airweave-backend python -c "import tiktoken; print('tiktoken version:', tiktoken.__version__)"

# 检查 tiktoken 缓存位置
docker exec airweave-backend python -c "import tiktoken; import os; print('Cache dir:', os.path.join(os.path.expanduser('~'), '.cache', 'tiktoken'))"

# 尝试手动加载 tiktoken 编码
docker exec airweave-backend python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); print('Encoding loaded:', enc.name)"
```

#### 3. 离线模式配置检查
```bash
# 检查是否配置了离线模式
docker exec airweave-backend env | grep -E "OFFLINE|TIKTOKEN|ENCODE"

# 检查 HF_HUB_LOCAL_FILES_ONLY 设置
docker exec airweave-backend env | grep HF_HUB
```

#### 4. 代码块处理器配置检查
```bash
# 查看代码块处理器的配置
docker logs airweave-backend | grep -i "CodeChunker\|tiktoken"

# 查看同步日志中的详细错误
docker logs airweave-temporal-worker --tail 50 | grep -i "tiktoken\|CodeChunker"
```

### 常见问题及解决方案

#### 问题 1: 网络连接问题导致 tiktoken 下载失败
**症状**: 无法访问 `openaipublic.blob.core.windows.net`
**检查**: DNS 解析或网络连接失败
**解决方案**:

**方法 1**: 手动下载并缓存 tiktoken 编码文件
```bash
# 在宿主机下载 tiktoken 编码文件
curl -o cl100k_base.tiktoken https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken

# 复制到容器中的 tiktoken 缓存目录
docker cp cl100k_base.tiktoken airweave-backend:/root/.cache/tiktoken/

# 验证文件已复制
docker exec airweave-backend ls -la /root/.cache/tiktoken/
```

**方法 2**: 使用代理或配置 DNS
```bash
# 配置 DNS 服务器
echo "nameserver 8.8.8.8" | docker exec -i airweave-backend sh -c "cat > /etc/resolv.conf"

# 或者在 docker-compose.yml 中配置 DNS
dns:
  - 8.8.8.8
  - 8.8.4.4
```

#### 问题 2: 代码块处理器不需要 tiktoken
**症状**: 代码文件同步不需要 token 编码
**检查**: 查看 source 的 chunker 配置
**解决方案**: 禁用 CodeChunker 或使用其他 chunker

#### 问题 3: tiktoken 缓存目录权限问题
**症状**: 无法写入缓存目录
**检查**: `docker exec airweave-backend ls -la /root/.cache/tiktoken/`
**解决方案**:
```bash
docker exec airweave-backend mkdir -p /root/.cache/tiktoken
docker exec airweave-backend chmod 755 /root/.cache/tiktoken
```

### 调试步骤

1. **验证 GitHub source 可以创建**
   ```bash
   # 创建 GitHub source connection（如果还未创建）
   # 在前端界面中完成 OAuth 授权
   ```

2. **检查同步日志**
   ```bash
   # 查看 temporal worker 日志
   docker logs airweave-temporal-worker --tail 100 | grep -A 10 "GitHub"

   # 查看后端日志中的错误
   docker logs airweave-backend --tail 100 | grep -i "tiktoken\|CodeChunker"
   ```

3. **测试网络连接**
   ```bash
   # 测试是否能解析域名
   docker exec airweave-backend nslookup openaipublic.blob.core.windows.net

   # 测试是否能访问
   docker exec airweave-backend wget --spider https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
   ```

4. **手动下载 tiktoken 编码文件**
   ```bash
   # 下载文件
   curl -L -o cl100k_base.tiktoken https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken

   # 复制到容器
   docker cp cl100k_base.tiktoken airweave-backend:/root/.cache/tiktoken/

   # 验证可以加载
   docker exec airweave-backend python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); print('Success:', enc.name)"
   ```

5. **重新触发同步**
   ```bash
   # 在前端界面中重新触发同步
   # 或者重启相关服务
   docker restart airweave-temporal-worker
   ```

### 相关日志位置

- **Temporal Worker 日志**: `docker logs airweave-temporal-worker`
- **后端日志**: `docker logs airweave-backend`
- **浏览器日志**: 浏览器开发者工具 Console 和 Network 标签

### 修复记录

#### 修复 1: 手动下载 tiktoken 编码文件
**日期**: 2026-04-10
**问题**: 网络问题导致 tiktoken 无法从 OpenAI 服务器下载编码文件，代码块处理器初始化失败
**症状**: `Failed to load tiktoken encoding 'cl100k_base': HTTPSConnectionPool(host='openaipublic.blob.core.windows.net', port=443): Max retries exceeded`
**解决**: 手动下载 tiktoken 编码文件并复制到容器缓存目录
**状态**: ✅ 已验证解决

**修复命令**:
```bash
# 1. 在宿主机下载文件
curl -L -o cl100k_base.tiktoken https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken

# 2. 创建容器缓存目录
docker exec airweave-backend mkdir -p /root/.cache/tiktoken

# 3. 复制文件到容器
docker cp cl100k_base.tiktoken airweave-backend:/root/.cache/tiktoken/

# 4. 验证加载
docker exec airweave-backend python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); print('Success:', enc.name)"
```

## Q4: 搜索功能失败，报错 LLM API "Model Not Exist"

### 问题症状
- 搜索功能无法正常工作
- 错误信息：`Internal Server Error: LLMFatalError: OpenAILLM API call fatal error (HTTP 400): Error code: 400 - {'error': {'message': 'Model Not Exist', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_request_error'}}`
- 搜索请求返回 500 错误

### 问题分析

#### 当前配置状态
```bash
# .env 文件中的配置
OPENAI_API_KEY=sk-31948c4537f64ae18c8c17b38e7a2774
OPENAI_BASE_URL=https://api.deepseek.com/v1
#OPENAI_MODEL_OVERRIDE=qwen2.5:7b-instruct  # 被注释掉
```

#### 问题根因
1. **配置不匹配**:
   - `OPENAI_BASE_URL` 指向 DeepSeek API
   - `OPENAI_MODEL_OVERRIDE` 未设置（被注释）
   - 系统使用 `defaults.yml` 中配置的模型名 `gpt-5-nano`

2. **模型名冲突**:
   - DeepSeek API 不支持 `gpt-5-nano` 模型名
   - DeepSeek 支持的模型：`deepseek-chat`, `deepseek-reasoner`
   - 当向 DeepSeek API 请求不存在的模型时，返回 "Model Not Exist" 错误

3. **代码逻辑**:
   - `backend/airweave/adapters/llm/openai.py` 第 88-89 行：
     ```python
     @property
     def _model_name(self) -> str:
         return settings.OPENAI_MODEL_OVERRIDE or self._model_spec.api_model_name
     ```
   - 当 `OPENAI_MODEL_OVERRIDE` 未设置时，使用 `api_model_name`（即 `gpt-5-nano`）
   - 模型名与 DeepSeek API 不兼容

### 解决方案

#### 方案 1: 设置正确的 DeepSeek 模型名（推荐）
```bash
# 在 .env 文件中取消注释并设置正确的 DeepSeek 模型名
OPENAI_MODEL_OVERRIDE=deepseek-chat
```

**DeepSeek 支持的模型**:
- `deepseek-chat` - 主要聊天模型
- `deepseek-reasoner` - 推理模型

#### 方案 2: 查询可用模型
```bash
# 查询 DeepSeek API 支持的模型列表
curl -s https://api.deepseek.com/v1/models -H "Authorization: Bearer YOUR_API_KEY"

# 预期输出：
# {"object":"list","data":[{"id":"deepseek-chat","object":"model","owned_by":"deepseek"},{"id":"deepseek-reasoner","object":"model","owned_by":"deepseek"}]}
```

### 验证步骤

#### 1. 修改配置
```bash
# 编辑 .env 文件
nano .env

# 取消注释并设置正确的模型名
OPENAI_MODEL_OVERRIDE=deepseek-chat
```

#### 2. 重启后端服务
```bash
docker-compose restart backend
```

#### 3. 验证配置
```bash
# 检查环境变量是否正确加载
docker logs airweave-backend --tail 20 | grep -E "OPENAI|model"

# 或者进入容器查看
docker exec airweave-backend env | grep OPENAI
```

#### 4. 测试搜索功能
- 访问前端界面
- 执行搜索操作
- 检查是否还有 "Model Not Exist" 错误

### 技术细节

#### 配置优先级
在 `backend/airweave/adapters/llm/openai.py` 中：
1. `OPENAI_MODEL_OVERRIDE` - 最高优先级（手动覆盖）
2. `_model_spec.api_model_name` - 从 defaults.yml 读取

#### DeepSeek API 特性
- OpenAI 兼容的 API 端点
- 使用不同的模型命名规则
- 需要 `OPENAI_BASE_URL` 指向 `https://api.deepseek.com/v1`
- 需要有效的 DeepSeek API key

### 相关文件

- **配置文件**: `.env`, `backend/airweave/search/defaults.yml`
- **LLM 适配器**: `backend/airweave/adapters/llm/openai.py`
- **LLM 注册表**: `backend/airweave/adapters/llm/registry.py`
- **搜索工厂**: `backend/airweave/core/container/factory.py`
- **后端日志**: `docker logs airweave-backend`

### 修复记录

#### 修复 1: DeepSeek API 模型检测逻辑问题
**日期**: 2026-04-10
**问题**: 使用 DeepSeek API 时，启动时模型自动检测失败，导致搜索功能报错 "Model Not Exist"
**症状**: 搜索功能失败，LLM API 返回 HTTP 400 错误
**根原因**:
1. 启动时 `fetch_local_models()` 从 DeepSeek API 返回空列表
2. `local_model_override` 保持为 `None`
3. 代码在 `factory.py` 第 1282-1285 行的条件判断只检查 `local_model_override`，没有检查 `OPENAI_MODEL_OVERRIDE`
4. 即使设置 `OPENAI_MODEL_OVERRIDE`，也不使用本地 model spec
5. 最终使用了 `defaults.yml` 中的错误模型名 `gpt-5-nano` 或 `gpt-4o-mini`
6. DeepSeek API 不支持这些模型名，返回 "Model Not Exist" 错误

**临时解决**: 在 `.env` 文件中设置 `OPENAI_MODEL_OVERRIDE=deepseek-chat`
**永久解决**: 修复 `factory.py` 中的模型检测逻辑，同时检查 `local_model_override` 和 `OPENAI_MODEL_OVERRIDE`
**状态**: 需要修复代码逻辑

**修复步骤**:
```bash
# 1. 临时解决：编辑 .env 文件
nano .env

# 2. 设置正确的 DeepSeek 模型名
OPENAI_MODEL_OVERRIDE=deepseek-chat

# 3. 重启后端
docker-compose restart backend

# 4. 测试搜索功能
# 访问前端界面，执行搜索操作
```

**代码修复建议**:
修改 `backend/airweave/core/container/factory.py` 第 1282-1285 行：
```python
# 修改前：
if (
    provider == LLMProvider.OPENAI
    and settings.OPENAI_BASE
    and local_model_override  # 只检查 local_model_override
):

# 修改后：
if (
    provider == LLMProvider.OPENAI
    and settings.OPENAI_BASE
    and (local_model_override or settings.OPENAI_MODEL_OVERRIDE)  # 同时检查两者
):
```