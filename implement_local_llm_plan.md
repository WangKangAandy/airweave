# Airweave 本地部署完整指南

## 概述

本文档记录了将 Airweave 从纯云端依赖改造为完全本地部署所做的所有修改。修改涵盖了 LLM 服务、Embedding 服务、数据库配置、Docker 容器配置等多个方面。

---

## 一、修改文件总览

| 序号 | 文件路径 | 修改类型 | 说明 |
|------|----------|----------|------|
| 1 | `backend/airweave/core/config/settings.py` | 修改 | 添加 OPENAI_BASE_URL 和 OPENAI_MODEL_OVERRIDE 配置项 |
| 2 | `backend/airweave/adapters/llm/registry.py` | 修改 | 添加 OPENAI provider 和 GPT_4O_MINI 模型 |
| 3 | `backend/airweave/adapters/llm/openai.py` | **新建** | OpenAI-compatible LLM 适配器，支持本地服务 |
| 4 | `backend/airweave/core/container/factory.py` | 修改 | 注册 OpenAI provider，实现动态 fallback 链 |
| 5 | `backend/airweave/domains/embedders/config.py` | 修改 | 修复 health check 端点（/health → /.well-known/ready） |
| 6 | `backend/airweave/domains/temporal/worker/__init__.py` | 修改 | OCR 变为可选依赖，不再强制要求 |
| 7 | `backend/airweave/platform/chunkers/semantic.py` | 修改 | 简化 SemanticChunker，离线模式下使用 TokenChunker |
| 8 | `backend/pyproject.toml` | 修改 | 添加 sentence-transformers 依赖 |
| 9 | `docker/docker-compose.yml` | 修改 | 多处服务环境变量修复 |
| 10 | `.env` | 修改 | 添加本地服务配置 |

---

## 二、详细修改说明

### 2.1 LLM 服务本地化

#### 2.1.1 添加配置项
**文件**: `backend/airweave/core/config/settings.py`

```python
# 添加的配置项
OPENAI_BASE_URL: Optional[str] = None
OPENAI_MODEL_OVERRIDE: Optional[str] = None
```

#### 2.1.2 注册 OPENAI Provider
**文件**: `backend/airweave/adapters/llm/registry.py`

```python
# LLMProvider 枚举添加
class LLMProvider(str, Enum):
    ...
    OPENAI = "openai"

# MODEL_REGISTRY 添加
LLMProvider.OPENAI: {
    LLMModel.GPT_4O_MINI: LLMModelSpec(
        api_model_name="gpt-4o-mini",
        context_window=128_000,
        max_output_tokens=16_384,
        required_tokenizer_type=TokenizerType.TIKTOKEN,
        required_tokenizer_encoding=TokenizerEncoding.O200K_HARMONY,
        thinking_config=ThinkingConfig(param_name="_noop", param_value=False),
        input_price_factor=0.075,
        output_price_factor=0.3,
    ),
}
```

#### 2.1.3 创建 OpenAI 适配器
**文件**: `backend/airweave/adapters/llm/openai.py` (**新建**)

核心功能：
- 支持自定义 `base_url` 指向本地 Ollama/vLLM
- 支持 `OPENAI_MODEL_OVERRIDE` 覆盖默认模型名
- 使用 dummy API key 绕过检查（本地模式）

#### 2.1.4 注册到容器工厂
**文件**: `backend/airweave/core/container/factory.py`

```python
# 添加导入
from airweave.adapters.llm.openai import OpenAILLM

# provider_classes 添加
provider_classes = {
    ...
    LLMProvider.OPENAI: OpenAILLM,
}

# 动态 fallback 逻辑
if settings.OPENAI_BASE_URL:
    llm_fallback_chain.insert(0, (LLMProvider.OPENAI, LLMModel.GPT_4O_MINI))

# 跳过 API key 检查（本地模式）
if provider == LLMProvider.OPENAI and settings.OPENAI_BASE_URL:
    pass  # 允许无 API key
```

---

### 2.2 Embedding 服务配置

#### 2.2.1 修复 Health Check 端点
**文件**: `backend/airweave/domains/embedders/config.py`

```python
# 原代码
health_url = f"{inference_url}/health"

# 修改后
health_url = f"{inference_url}/.well-known/ready"
```

#### 2.2.2 Docker 网络配置
**文件**: `docker/docker-compose.yml`

```yaml
# backend 服务
- TEXT2VEC_INFERENCE_URL=http://host.docker.internal:9878

# temporal-worker 服务
- TEXT2VEC_INFERENCE_URL=http://airweave-embeddings:8080
```

> **注意**: 需要在 docker-compose 中配置 `extra_hosts: host-gateway`

---

### 2.3 数据库认证修复

#### 2.3.1 Temporal 服务
**文件**: `docker/docker-compose.yml`

```yaml
temporal:
  environment:
    - POSTGRES_USER=airweave
    - POSTGRES_PWD=8pp1npkF9gXrFbOQsDSfiQ
```

#### 2.3.2 SVIX 服务
**文件**: `docker/docker-compose.yml`

```yaml
svix:
  environment:
    - SVIX_DB_DSN=postgresql://airweave:8pp1npkF9gXrFbOQsDSfiQ@postgres:5432/svix
    - SVIX_JWT_SECRET=local-dev-svix-jwt-secret-that-is-at-least-32-chars
```

---

### 2.4 OCR 依赖处理

**文件**: `backend/airweave/domains/temporal/worker/__init__.py`

```python
# 原代码（强制要求）
if container_mod.container.ocr_provider is None:
    logger.error(...)
    raise SystemExit(1)

# 修改后（可选）
if container_mod.container.ocr_provider is None:
    logger.warning(
        "No OCR backend available - document processing will be disabled. "
        "Text-based sources like GitHub will still work."
    )
```

---

### 2.5 Chunker 离线适配

**文件**: `backend/airweave/platform/chunkers/semantic.py`

```python
def _ensure_chunkers(self):
    """离线模式：只使用 TokenChunker，不尝试加载 SemanticChunker"""
    if self._token_chunker is not None:
        return
    
    from chonkie import TokenChunker
    
    tokenizer = get_tokenizer(self.TOKENIZER)
    self._tiktoken_tokenizer = tokenizer
    
    if not isinstance(tokenizer, TikTokenTokenizer):
        self._token_chunker = None
        logger.warning("No tiktoken available, chunking will use basic splitting")
        return
    
    safe_encoding = SafeEncoding(tokenizer.encoding)
    self._token_chunker = TokenChunker(
        tokenizer=safe_encoding,
        chunk_size=self.MAX_TOKENS_PER_CHUNK,
        chunk_overlap=0,
    )
    logger.info("Initialized TokenChunker (offline mode, no semantic chunking)")
```

**依赖更新**:
**文件**: `backend/pyproject.toml`

```toml
sentence-transformers = "^3.0"
```

---

## 三、.env 配置模板

```bash
# ==================== LLM 配置（本地 Ollama/vLLM） ====================
OPENAI_API_KEY=ollama
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL_OVERRIDE=qwen2.5:7b-instruct

# ==================== Embedding 配置（本地 text2vec） ====================
DENSE_EMBEDDER=local_minilm
EMBEDDING_DIMENSIONS=384
TEXT2VEC_INFERENCE_URL=http://localhost:9878

# ==================== 其他配置 ====================
SPARSE_EMBEDDER=null
```

---

## 四、启动步骤

### 4.1 启动本地服务

```bash
# 启动 Ollama（如果使用本地 LLM）
ollama serve
ollama pull qwen2.5:7b-instruct

# 启动 text2vec-transformers（如果使用本地 Embedding）
docker run -d -p 9878:8080 --name text2vec ghcr.io/hkunlp/text2vec-transformers:latest
```

### 4.2 启动 Airweave

```bash
cd /home/andy/airweave-main
./start.sh --noninteractive
```

### 4.3 验证

```bash
# 检查容器状态
docker ps | grep airweave

# 检查 sync 状态
docker exec airweave-db psql -U airweave -d airweave -c "SELECT status, entities_inserted FROM sync_job ORDER BY started_at DESC LIMIT 1;"
```

---

## 五、故障排除

### 问题 1: Embedding 超时

**现象**: `Local embedding request timed out`

**原因**: 本地 embedding 服务响应较慢

**解决**: 这是正常现象，等待同步完成即可

### 问题 2: Sync 卡住

**现象**: status 一直是 "running"，entities 一直是 0

**解决**:
```bash
# 重启 temporal worker
docker restart airweave-temporal-worker

# 检查日志
docker logs airweave-temporal-worker --tail 50
```

### 问题 3: SemanticChunker 失败

**现象**: `Failed to load embeddings via SentenceTransformerEmbeddings`

**原因**: 离线环境下无法下载模型

**解决**: 已修改为使用 TokenChunker，参考 2.5 节

---

## 六、架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Airweave 本地部署                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Ollama     │    │  text2vec    │    │   Vespa      │      │
│  │  (LLM)       │    │ (Embedding) │    │ (Vector DB)  │      │
│  │              │    │              │    │              │      │
│  │ :11434/v1    │    │   :9878      │    │   :8081     │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                   │                   │                │
│         └───────────────────┼───────────────────┘                │
│                             │                                    │
│                    ┌────────▼────────┐                          │
│                    │  Docker Network │                          │
│                    │  (host-gateway) │                          │
│                    └────────┬────────┘                          │
│                             │                                    │
│  ┌──────────────────────────▼──────────────────────────┐        │
│  │                    Airweave 容器                      │        │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────┐         │        │
│  │  │ Backend │  │ Temporal │  │   Frontend  │         │        │
│  │  │  :8001  │  │  Worker  │  │    :8080    │         │        │
│  │  └─────────┘  └─────────┘  └─────────────┘         │        │
│  └──────────────────────────────────────────────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 七、总结

本次改造实现了以下目标：

1. ✅ **LLM 本地化** - 支持 Ollama/vLLM，通过 OPENAI_BASE_URL 配置
2. ✅ **Embedding 本地化** - 支持 text2vec-transformers，配置 local_minilm
3. ✅ **离线运行** - TokenChunker 替代 SemanticChunker，无网络也能运行
4. ✅ **无 API Key** - 纯本地服务，无需任何云 API Key
5. ✅ **数据库认证修复** - Temporal、SVIX 服务使用正确凭据

所有修改都已持久化到源代码中，重新部署时只需：
1. 启动本地服务（Ollama、text2vec）
2. 执行 `./start.sh --noninteractive`
3. 触发同步测试