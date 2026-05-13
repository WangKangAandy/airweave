# 钉钉云文档接入方案（实现导向版）

## 1) 接入目标（先定义边界）

- 平台名称：钉钉云文档（Dingtalk）
- 本期目标（MVP）：支持企业内部应用直连，完成正文读取、全量同步、搜索命中
- 非目标（本期不做）：完整 ACL 执行、全类型附件解析、跨租户第三方应用全面覆盖
- 预期用户价值：可检索（MVP），后续补可增量、可删除检测

### MVP 建议范围

- 可创建 Source Connection
- 支持至少一种核心内容类型（文档正文，非仅元数据）
- 可完成一次全量同步并在搜索命中
- MVP `operator_mode` 仅支持 `fixed_admin`，不实现 `bind_per_connection`

### MVP 索引边界声明（必须明确）

- 本期索引边界：按应用 + operator 可见性索引（不是最终用户级可见性）
- 本期不做 per-user ACL filter，但必须保留 ACL 补齐所需字段
- 搜索结果可能存在“超出提问用户可见范围”的风险，需在产品侧标注 Beta 边界

### MVP 上线门槛（安全与产品）

- 若产品侧无法展示 Beta 风险提示，则禁止对普通用户开放 DingTalk source
- 默认仅对 admin 或 internal workspace 开启
- 搜索结果页需展示来源与权限边界说明（按应用 + operator 可见域）

## 2) 官方能力调研结论

### 2.1 官方文档（已验证）

- 如何调用服务端 API：<https://developers.dingtalk.com/document/app/how-to-call-apis>
- 获取企业内部应用 accessToken：<https://developers.dingtalk.com/document/app/obtain-the-access_token-of-an-internal-app>
- 调用频率限制：<https://developers.dingtalk.com/document/app/invocation-frequency-limit-1>
- 获取空间下所有文件或文件夹列表：<https://open.dingtalk.com/document/isvapp-server/get-the-list-of-files-or-folders-under-a-space>
- 查询块元素：<https://open.dingtalk.com/document/development/api-docblocksquery>
- 块元素数据结构：<https://open.dingtalk.com/document/development/block-data-structure>
- 订阅文件变更事件：<https://open.dingtalk.com/document/orgapp/subscribe-to-file-change-events>
- 取消订阅文件变更事件：<https://open.dingtalk.com/document/development/unsubscribe-from-file-change-events>

### 2.2 可行性结论（当前）

- 是否支持服务端读取：是（企业内部应用）
- 是否依赖企业权限配置：是（需在开发者后台开通对应 API 权限）
- 鉴权主方案：企业内部应用 `appKey + appSecret -> accessToken`
- token 有效期：7200 秒，建议缓存 7000 秒并自动续期
- 正文能力形态：存在结构化块元素能力，正文链路需优先按“块树聚合”设计
- 发现能力形态：存在 space 级平铺列表与 folder 级非递归列表，需双模式发现
- 操作人上下文：部分接口依赖 `unionId/operatorId`，不可仅按 app 身份假设全可见
- 限流需重点处理：接口级 + 应用级 + IP 级（含 900xx 错误码与 IP 惩罚）

## 3) Airweave 对标调研结论（复用路线）

### 3.1 主参考 A：Feishu Connector（入口解析与发现模式）

推荐主参考 `backend/airweave/platform/sources/feishu.py`，原因：

- 都是“文档 + 文件夹”形态
- 都适合“业务入口解析 -> 文档 ID 归一化”
- 都有“入口多形态（folder/doc）归一化”的需求

可重点复用：

- resolver 设计：`platform/sources/resolvers/feishu.py`
- 入口归一化与去重：`resolve_many()` + invalid 收集
- direct credentials + provider token 双模式鉴权

### 3.2 主参考 B：Notion Connector（正文结构化，提升为同级）

参考 `backend/airweave/platform/sources/notion.py`：

- 块级内容递归抽取 -> markdown 聚合
- 附件块转 `FileEntity` 的处理链
- parent/breadcrumb 信息补齐

适用场景：钉钉正文走块元素接口时，可直接借鉴其“块树 -> 统一文本”的主链路。

### 3.3 增量/删除参考：Google Drive Connector

参考 `backend/airweave/platform/sources/google_drive.py`：

- change token 增量方案
- `DeletionEntity` 删除事件建模
- metadata diff 控制重复更新

钉钉已存在文件变更订阅能力，建议 Phase 2 优先评估事件流；时间戳增量作为兜底。

## 4) 鉴权与配置设计

### 4.1 配置字段（建议）

- 必填凭证：
  - `app_key`
  - `app_secret`
- 必填定位参数：
  - 业务链接列表 `links`（唯一用户输入入口）
- 默认/隐藏参数（不在 UI 暴露）：
  - `operator_mode=fixed_admin`
  - `discovery_mode=space_full`
  - `max_folder_depth=5`
  - `include_content_types=["doc"]`
  - `permission_mode=app_operator_scope`
- 可选高级参数：
  - `operator_union_id`（仅在租户接口强依赖 operator 上下文时填写）
- 可选参数：
  - `root_space_id` / `root_folder_id`（仅保留后端兼容，不建议新连接使用）

### 4.2 鉴权流程

1. 通过 `appKey/appSecret` 调 `POST /v1.0/oauth2/accessToken`
2. 缓存 token（7000s）并在请求头带 `x-acs-dingtalk-access-token`
3. 若配置了 `operator_union_id`，请求附带 operator 上下文；若未配置，先按应用可见域探测
4. 401/凭证失效时刷新 token，重试一次
5. 429/900xx 走统一退避重试

### 4.3 operator 上下文策略（新增）

- `fixed_admin`：固定管理员 `unionId` 作为同步上下文（实现固定，但默认不强制用户填写）
- `bind_per_connection`：每个连接绑定独立 operator（Phase 3/后续增强，不在 MVP 实现）
- validate 需拆分为两段：
  - auth validate：token 可获取
  - scope validate：可列举 + 可读取正文（防止假阳性）；若接口返回“需要 operator”再提示补填 `operator_union_id`
- 错误分类补充：
  - `AUTH_OK_BUT_EMPTY_SCOPE`
  - `OPERATOR_NO_PERMISSION`

### 4.4 入口解析建议

- 后端新增 `DingTalkEntryResolver`（批量解析链接、token、ID）
- 前端支持批量输入（空格/逗号/分号/换行）
- 提交前给出 `X accepted, Y invalid`

## 5) Airweave 代码接入清单（可执行）

### 5.1 后端文件新增/改造

1. `backend/airweave/platform/configs/auth.py`  
   新增 `DingtalkAuthConfig`
2. `backend/airweave/platform/configs/config.py`  
   新增 `DingtalkConfig`
3. `backend/airweave/platform/entities/dingtalk_docs.py`  
   新增实体定义（MVP 至少 `DingTalkDocEntity`）
4. `backend/airweave/platform/sources/dingtalk_docs.py`  
   新增 source 实现（`create/validate/generate_entities`）
5. `backend/airweave/platform/sources/resolvers/dingtalk.py`  
   新增入口解析器（推荐）
6. `backend/airweave/platform/cursors/dingtalk_docs.py`  
   新增增量游标（Phase 2）
7. 注册项更新：
   - `platform/sources/__init__.py`
   - `platform/entities/__init__.py`
   - `platform/cursors/__init__.py`
8. 搜索描述补齐（关键）：
   `backend/airweave/domains/search/builders/collection_metadata.py`
9. 事件订阅适配（Phase 2）：
   - 订阅/取消订阅接口对接
   - 事件消费与去重管道

### 5.2 前端文件（按需）

- 图标：`frontend/src/components/icons/apps/dingtalk.svg`
- 配置扩展：
  - `frontend/src/components/shared/views/panel/SourceConfigView.tsx`
  - 推荐新增扩展：`source-config-extensions/dingtalk.ts`

## 6) 实体与同步策略设计（建议）

### 6.1 实体建模（MVP）

- `DingTalkDocEntity`
  - 主键：统一 `entity_id`（稳定外部 ID），格式 `dingtalk:{resource_type}:{resource_id}`
  - MVP `resource_type` 固定为 `doc`，示例：`dingtalk:doc:{doc_id_or_uuid}`
  - 核心字段：`title`、`raw_content`、`space_id`、`parent_id`、`path`、`created_at`、`updated_at`、`url`
  - 内容可观测字段：
    - `content_source`：`block_tree` / `direct_api` / `fallback`
    - `content_status`：`success` / `partial` / `empty` / `unsupported` / `failed`
  - ACL 预留字段：`owner_id`、`permission_mode`、`operator_id`

### 6.2 正文提取路径（钉死）

- 路径优先级：
  1) 文档块元素接口（block tree）
  2) 官方可用的正文直取接口（若目标类型支持）
  3) 其他兜底抽取路径（仅兜底，不作为主链路）
- 聚合策略：块树递归 -> markdown 聚合 -> `raw_content`
- MVP 最小覆盖：标题、段落、列表、代码块
- 明确非目标：复杂嵌入、富媒体深度语义还原
- 成功/失败判定（必须统一）：
  - `raw_content.strip()` 非空：`content_status=success`
  - 仅获取到标题，或仅获取到部分正文内容但未达到完整正文抽取标准：`content_status=partial`
  - 接口可访问但返回空块：`content_status=empty`
  - 类型不支持正文聚合：`content_status=unsupported`
  - 调用或解析异常：`content_status=failed`

### 6.3 发现与遍历策略（双模式）

- `space_full`：space 级平铺枚举（优先用于全量和断点恢复）
- `folder_scoped`：root folder 定向枚举（非递归接口 + 可控递归）
- 默认建议：MVP 首次全量使用 `space_full`，兼容 `folder_scoped` 精准接入

### 6.4 同步策略

- Phase 1：全量同步（分页 + 双模式发现）
- Phase 2：增量同步（优先事件订阅，其次 `updated_time` 游标兜底）
- Phase 3：删除检测（优先事件驱动删除 + orphan cleanup 兜底）

### 6.5 事件幂等与重放规则（Phase 2 必须落实）

- 幂等键：
  - 优先使用平台 `event_id`
  - 若无稳定 `event_id`，使用 `resource_id + event_type + event_time` 组合键
- 重放容忍：
  - 同一事件重复到达只处理一次（幂等写）
  - 删除事件先写 tombstone，再异步 cleanup
- 顺序处理：
  - 不假设事件严格有序
  - 若删除后收到旧更新事件，以 `updated_at/event_time` 比较，旧事件忽略

### 6.6 错误处理与重试

- 推荐复用：
  - `platform/sources/http_helpers.py::raise_for_status`
  - `platform/sources/retry_helpers.py`
- 错误映射基线：
  - 401：凭证失效
  - 403：权限不足或资源不可见
  - 200 + 空列表：需区分“确实无数据”与“operator 可见域不足”
  - 429 / 900xx：限流（退避重试）
  - 5xx：上游波动（可重试）

## 7) 分阶段落地计划

### Phase 1（3-5 天）

- Direct 鉴权 + token 缓存
- 双发现模式打通（`space_full` + `folder_scoped`）
- 正文块树聚合链路打通（核心类型）
- operator 策略落地（推荐 `fixed_admin`）
- `DingTalkDocEntity` 入库
- 全量同步 + 搜索命中

### Phase 2（2-4 天）

- 文件变更订阅/取消订阅能力评估并接入
- 事件驱动增量 + 删除事件接入
- 时间戳 cursor 兜底路径完善
- 重试与限流策略强化
- validate 错误信息可读化

### Phase 3（3-6 天）

- 删除检测完善
- 入口解析器与批量输入体验
- 附件与富媒体类型扩展
- ACL 补齐（索引过滤链路）

## 8) 风险与排障建议

### 8.1 主要风险

- API 权限开通不足导致 403
- 文档类型/正文格式分裂，需做统一转换层（block -> markdown）
- operator 策略不明确导致 validate 假阳性（能鉴权但无可读数据）
- 限流触发（尤其 IP 维度）导致批量同步抖动
- 事件消费去重与重放策略不足导致重复写入/漏删
- 本期未做 per-user ACL 过滤带来的权限泄漏风险

### 8.2 排障 checklist

- [ ] 开发者后台已为应用开通目标 API 权限
- [ ] accessToken 获取与缓存逻辑可观测
- [ ] operator_union_id 已配置并通过可见域探测
- [ ] 同步日志包含 `source_short_name/request_id/sync_job_id`
- [ ] 403/429/900xx/5xx 已分类并可定位
- [ ] classic search 无 source description 缺失问题

## 9) 验证清单（联调）

### 9.1 创建连接

- [ ] UI 创建 Source Connection 成功
- [ ] validate 能区分“凭证错误”与“权限不足”
- [ ] validate 能识别“operator 未配置/可见域不足”

### 9.2 同步

- [ ] 至少完成 1 次全量同步
- [ ] `entities_inserted > 0`
- [ ] worker 日志无 `Source not found: dingtalk`
- [ ] 正文字段来源可追溯（块接口聚合链路可观测）

### 9.3 搜索

- [ ] classic search 可返回钉钉文档结果
- [ ] 新增实体可按标题/正文命中
- [ ] metadata 包含 `space_id/owner_id/path/permission_mode/operator_id`

## 10) 后续增强 TODO

- [ ] ACL（用户/部门/群组可见性）映射
- [ ] 目录移动/重命名检测
- [ ] 附件与富媒体抽取
- [ ] 事件驱动增量与删除链路生产化

## 11) 非功能约束

### 11.1 可观测性

- token 刷新次数与失败次数可观测
- API 429/403 比例可观测（按接口维度）
- `content_status` 分布可观测
- full sync 过程指标可观测：发现数 / 成功抽取数 / 空内容数 / 失败数

### 11.2 幂等性

- 同一资源重复同步不得产生重复实体
- 同一事件重复消费不得重复写入

### 11.3 性能目标（MVP 基线）

- 单次全量同步目标支持：`1k-5k` 文档级别（占位基线，后续按压测修订）
- 单接口并发上限：`2-5`（保守默认，按限流反馈动态调整）
- 限流触发最大退避时长：`60s-120s`（含抖动）

### 11.4 安全边界

- secret 禁止写入日志
- `operator_union_id` 输出日志时必须脱敏
- 403/401 错误信息不得泄露敏感上下文

## 12) 联调切换清单（真实 DingTalk API 映射）

> 目的：将当前实现中的占位路径/字段映射替换为租户真实可用 API 形态，确保发现、正文、状态判定与日志一致。

### 12.1 认证链路

- 目标能力：`app_key/app_secret -> accessToken`
- 当前代码落点：`backend/airweave/platform/sources/dingtalk_docs.py::API_PATHS.token`
- 联调核对项：
  - [ ] 请求路径与方法确认（`POST`）
  - [ ] 请求体字段名确认（`appKey/appSecret` 是否一致）
  - [ ] 响应 token 字段名确认（`accessToken` 或其他）
  - [ ] token 过期码/错误码确认（401/403/业务码）

### 12.2 发现链路（space / folder）

- 目标能力：
  - space 枚举文件/文件夹
  - folder 枚举文件/文件夹（含分页）
- 当前代码落点：
  - `API_PATHS.space_files`
  - `API_PATHS.folder_files`
  - `_extract_items()`（响应列表字段提取）
- 联调核对项：
  - [ ] 分页参数名确认（`cursor/size` 是否一致）
  - [ ] 下一页游标字段名确认（`nextCursor` 或其他）
  - [ ] item 类型字段确认（`type/item_type/resource_type`）
  - [ ] doc id 字段确认（`doc_id/docId/dentry_uuid/...`）
  - [ ] folder id 字段确认（是否与 doc id 复用字段）
  - [ ] 空列表语义确认（确无数据 vs 可见域不足）

### 12.3 正文主链路（block tree）

- 目标能力：按 doc 获取 block tree 并聚合文本
- 当前代码落点：
  - `API_PATHS.doc_blocks`
  - `_get_doc_blocks()`
  - `_flatten_block_text()`
- 联调核对项：
  - [ ] block 列表字段名确认（`items/list/blocks`）
  - [ ] block 文本字段层级确认（`text/plain_text/rich_text/...`）
  - [ ] 分页字段确认（与发现链路一致或差异化）
  - [ ] 无块返回语义确认（空正文 vs 不支持）

### 12.4 正文备链路（direct_api + fallback）

- 目标能力：
  - direct_api：正文直取
  - fallback：元数据兜底抽取
- 当前代码落点：
  - `API_PATHS.doc_content`
  - `API_PATHS.doc_meta`
  - `_extract_doc_content_direct_api()`
  - `_extract_doc_content_fallback()`
- 联调核对项：
  - [ ] 正文直取接口是否真实可用（按文档类型）
  - [ ] 正文字段名确认（`content` 或其他）
  - [ ] 元数据可用文本字段确认（`summary/description/...`）
  - [ ] 不支持正文类型的可识别信号确认（错误码/类型字段）

### 12.5 `content_source/content_status` 口径校验

- 当前实现口径：
  - `content_source`：`block_tree` / `direct_api` / `fallback`
  - `content_status`：`success` / `partial` / `empty` / `unsupported` / `failed`
- 联调核对项：
  - [ ] block 有内容 -> `block_tree + success`
  - [ ] block 空、direct 有内容 -> `direct_api + success`
  - [ ] 多链路都无有效正文且类型不支持 -> `fallback + unsupported`
  - [ ] 可访问但确无正文 -> `empty`
  - [ ] 接口异常/权限失败 -> `failed`

### 12.6 最小验收样本（建议）

- 样本集合（至少各 1 个）：
  - [ ] 标准文档（可完整正文）
  - [ ] 仅标题文档（验证 `partial`）
  - [ ] 空文档（验证 `empty`）
  - [ ] 不支持正文类型（验证 `unsupported`）
  - [ ] 无权限文档（验证 `failed`）
- 验收输出：
  - [ ] 同步日志包含每 doc 最终 `source/status`
  - [ ] 汇总日志包含 `content_status` 分布
  - [ ] 实体入库后可按标题/正文命中

## 13) 图标问题复盘（基础错误，必须避免）

### 13.1 遇到的坎

- 早期图标并非直接使用网络可追溯来源，出现了“占位/手工近似”的错误路径。
- 下载阶段遇到多个外部源不稳定问题（404、429、超时），但中间处理一度错误地使用了“用户随手截图”作为替代。
- 结果是图标资产可追溯性差，且容易引发“视觉接近但非标准品牌图标”的偏差。

### 13.2 根因

- 没有把“图标必须来自可追溯网络来源”设为硬约束。
- 失败处理流程不够严格：下载失败后没有坚持“继续换源并记录失败证据”，而走了临时替代。
- 文档缺少图标资产来源与验收标准，导致执行时可操作规范不明确。

### 13.3 固化后的强制规则

- 图标只允许来自可追溯网络来源（官方品牌资产页或可信 logo 仓库），并在文档中记录来源 URL。
- 禁止使用截图、手绘、位图 base64 内嵌作为最终 `apps/<platform>.svg` 资产。
- 当下载失败时，必须：
  1) 继续切换可信来源；
  2) 记录失败 URL 与错误类型（404/429/timeout）；
  3) 未拿到可追溯 SVG 前，不得宣布完成图标接入。
- 合入前验证：
  - `frontend/src/components/icons/apps/dingtalk.svg` 为标准 SVG 资产；
  - UI 刷新后视觉与官方图标一致；
  - 文档可回溯图标来源。
