# 飞书文档接入主方案（DIRECT）配置与验证指南

> 目标：用 Airweave 接入飞书文档，采用主方案 `app_id + app_secret + Feishu Links`，并通过“测试文档同步”验证可行性。

## 一句话结论

对于 Airweave 这类“服务端持续同步”场景，主方案应采用 **DIRECT 模式**：

- 凭证：`app_id` + `app_secret`
- 范围：`Feishu Links`（支持 Folder / Wiki / Docx，支持批量）
- 服务端获取：`tenant_access_token`

该方案与飞书官方服务端鉴权模型一致，适合作为生产主路径。

---

## 1. 官方依据（关键文档）

- 飞书：自建应用获取 `tenant_access_token`  
[https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal](https://open.feishu.cn/document/server-docs/authentication-management/access-token/tenant_access_token_internal)
- 飞书：获取 `user_access_token`（OAuth 授权码流程）  
[https://open.feishu.cn/document/authentication-management/access-token/get-user-access-token](https://open.feishu.cn/document/authentication-management/access-token/get-user-access-token)

为什么主推 DIRECT：

- `tenant_access_token` 是服务端标准调用凭证，天然适配后台同步任务
- OAuth `user_access_token` 更偏“用户授权后即时访问”，不适合当唯一同步路径

---

## 2. 前置准备

在飞书开放平台完成：

1. 创建自建应用（Custom App）
2. 获取 `app_id`、`app_secret`
3. 开通云文档读取相关权限（Drive / Docx 只读能力）
4. 将应用安装到目标租户，并确保测试账号有应用使用权限

> 注意：若权限未开通或应用未安装，Airweave 侧通常会在创建连接时校验失败。

---

## 3. 准备飞书入口链接（Folder / Wiki / Docx）

建议先准备测试目录（例如 `Airweave-Feishu-Test`）和测试文档。  
当前 Airweave 已支持直接粘贴飞书分享链接，不要求用户手工提取 token。

参考下图（按图中步骤进入目录分享并复制链接）：

飞书分享入口获取示意图

输入格式说明：

- 支持 `folder`：`https://my.feishu.cn/drive/folder/<token>?...`
- 支持 `wiki`：`https://my.feishu.cn/wiki/<token>?...`
- 支持 `docx`：`https://my.feishu.cn/docx/<token>?...`
- 支持批量输入：可用空格、逗号、分号、换行分隔多个链接/标识
- 支持前缀形式：`folder:<token>` / `wiki:<token>` / `docx:<token>`

系统会自动做规范化与去重；无效项会在前端实时提示。

---

## 4. Airweave 配置（主方案）

在 Airweave 前端：

1. 选择 `Feishu` source
2. 认证方式选 DIRECT
3. 填入：
  - `app_id`
  - `app_secret`
4. 配置项填入：
  - `Feishu Links`（原 `folder_token` 字段，现面向用户以链接方式展示）
  - `max_folder_depth`（建议先填 `2` 或 `3`）
5. 创建连接并触发首次同步

创建前校验：

- 前端会实时显示：`Validation: X accepted, Y invalid`
- 点击 Create 前会做前置校验，若存在 invalid 则阻止提交并提示

---

## 5. 当前技术适配范围（MVP）

### 接口适配

- 文件发现：`drive/v1/files`（按目录遍历，递归进入子目录）
- 内容拉取：`docx/v1/documents/{token}`、`docx/v1/documents/{token}/raw_content`

### 实体映射

- `FeishuDocxEntity`
  - 主键：`doc_token`
  - 关键字段：`title`、`raw_content`、`url`、`created_time`、`updated_time`

---

## 6. 用“测试文档”验证同步是否可行

在上面的测试目录里新建一篇飞书文档（docx），内容写入唯一标记，例如：

`AIRWEAVE_FEISHU_SYNC_E2E_20260416`

然后执行验证：

1. 在 Airweave 触发该 Source Connection 的同步
2. 等待任务完成（状态变为成功）
3. 在 Airweave 搜索该唯一标记
4. 命中该文档即表示主方案链路打通

判定标准：

- 能创建连接（鉴权通过）
- 能完成至少 1 次同步
- 能在搜索中命中测试文档文本

---

## 7. 常见失败与排查

### 1) `tenant_access_token` 获取失败

常见原因：

- `app_id` / `app_secret` 错误
- 应用未安装到目标租户
- 应用状态异常（未启用）

### 2) 连接创建成功但拉不到文档

常见原因：

- 链接或 token 无效（格式正确但目标不存在/不可访问）
- 目录下没有 `docx` 文档
- 文档权限对应用不可见

### 3) 同步成功但检索不到

常见原因：

- 文档内容为空或仅图片
- 同步后索引尚未完成（可稍等重试）

### 4) UI 显示 pending，但后端已失败

常见原因：

- 前端状态未及时刷新，出现“看起来 pending”的错觉
- 实际任务已在后端 `sync_job` 中进入 `failed`

排查建议：

- 以数据库/后端任务状态为准（不要只看前端卡片）
- 明确记录 `sync_job_id`，按任务维度核对状态和错误信息

### 5) 修改代码后仍报旧错误

常见原因：

- 执行同步的 worker 进程未重启，仍在运行旧内存代码

排查建议：

- 区分 API 容器与实际执行同步的 worker 容器
- 涉及 source 运行逻辑变更后，确保 worker 重启并加载新代码

---

## 8. 已知风险与注意事项

- `raw_content` 接口频控较敏感，必须严格限流
- 企业内权限模型复杂，常见为“应用权限 + 资源权限”双层校验
- 飞书文档类型有差异（doc/docx/wiki/sheet），当前主链路以 docx 为核心

---

## 9. 建议的生产化增强（后续）

- 增量同步（按 `modified_time`）
- 删除检测（目录移除、文档删除）
- 更细粒度限流（按接口配额）
- ACL 映射（文档可见性）

---

## 10. 验证清单（可复用）

- [ ] 能创建连接并通过 validate
- [ ] 能拉到至少 1 篇 docx 正文
- [ ] 能完成一次全量同步并被搜索命中
- [ ] token 过期后可自动恢复

---

## 11. 当前结论

`app_id/app_secret + Feishu Links` 作为飞书接入主方案是可行且合理的。  
若你需要“用户授权体验”，可以额外提供 OAuth 模式，但不建议替代主方案。

---

## 12. 飞书适配全过程复盘（实战）

### 阶段 A：先打通最小主链路（手动同步）

- 先确保 DIRECT 鉴权链路稳定：`app_id + app_secret -> tenant_access_token`
- 以“可稳定手动同步并检索命中”为首要目标
- 用真实测试文档做闭环验证（创建连接 -> 触发同步 -> 搜索命中）

### 阶段 B：从“开发者输入 token”升级为“用户输入链接”

- 字段命名改为用户可理解语义（`Feishu Links`）
- 支持直接粘贴分享链接，自动解析 token
- 兼容 Folder / Wiki / Docx，不要求用户理解底层对象差异

### 阶段 C：扩展为批量输入 + 前置校验

- 支持一次输入多个链接（空格/逗号/分号/换行分隔）
- Create 前执行前置校验，避免任务提交后才失败
- 前端实时反馈 `accepted/invalid`，显著降低试错成本

### 阶段 D：架构抽象与收敛

- 后端把批量解析抽象为通用 `BatchEntryResolver`
- 飞书实现 `FeishuEntryResolver` 作为 source 特化插件
- 前端把飞书解析从通用 `SourceConfigView` 抽离到扩展脚本

收益：保持通用框架简洁，同时允许 source 特性独立演进。

### 阶段 E：线上故障定位（pending 误判）

- 现象：UI 一直 pending
- 实际：后端任务已失败，且曾出现 worker 未加载新代码导致旧逻辑执行
- 处理：重启实际执行同步的 worker，并按 `sync_job` 核验最终状态

结论：状态判断以任务系统事实为准，不以单一 UI 展示为准。

---

## 13. 可复用到其他 Source 的通用方法论

### 1) 产品输入层：让用户贴“业务对象链接”，不是技术 token

- 优先接受链接，系统自动解析并标准化
- 支持批量输入与容错分隔符
- 用“X accepted, Y invalid”做即时反馈

### 2) 解析层：通用基类 + Source 插件实现

- 把“批量拆分、去重、无效收集”下沉到基类
- Source 只实现 `resolve_one()` 的领域逻辑
- 为后续接入钉钉、企业微信、Confluence 等复用同一骨架

### 3) 验证层：提交前校验 + 运行前最小连通性校验

- 前端拦截明显无效输入，减少无效任务
- 后端 `validate` 做最小 API 探测，尽早失败并给出可读错误

### 4) 同步层：入口类型统一收敛到实体流

- 无论入口是 Folder / Wiki / Docx，最终都落到统一实体输出管道
- 加去重（如 `seen_doc_tokens`）与增量游标，避免重复与全量回扫

### 5) 运维层：排障优先看任务事实，再看展示层

- 优先核对 `sync_job` 真实状态和错误码
- 变更同步逻辑后，确保 worker 真正加载新代码
- 对外沟通时区分“显示 pending”和“任务失败”的语义差异

---

## 14. 事件订阅与长连接（放在最后的边界说明）

- 实战中曾评估并实现过飞书事件订阅/长连接能力，但已从当前主路径移除
- 当前建议：飞书接入以“DIRECT + 手动/定时同步”为主，保证稳定可交付
- 关于事件订阅能力的结论：需以飞书平台权限与应用类型边界为前提，尤其关注企业应用约束
- 对外沟通建议：将“事件订阅/长连接”定义为后续增强项，不作为当前验收必选