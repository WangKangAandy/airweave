# 国内平台接入文档模板（可复用）

> 用途：每新增一个平台时，复制本模板为 `docs/china-platforms/<platform>.md`，按章节补全。

## 1) 接入目标（先定义边界）

- 平台名称：
- 本期目标（MVP）：
- 非目标（本期不做）：
- 预期用户价值（可检索 / 可联邦 / 可增量）：

示例（MVP 常见边界）：
- 支持创建 Source Connection
- 支持至少一种核心内容类型（如文档正文）
- 支持一次全量同步并可被搜索命中

## 2) 官方能力调研结论（必须先做）

### 2.1 官方文档与 API

- 开放平台文档链接：
- 鉴权文档链接：
- 内容读取文档链接：
- 限流文档链接：

### 2.2 可行性结论

- 是否支持服务端读取：是/否
- 是否依赖企业审核：是/否（说明影响）
- 权限模型：应用权限 + 资源权限（或其他）
- 推荐主方案：OAuth / 直填凭证 / PAT / 混合

## 3) 鉴权与配置设计

### 3.1 配置字段（Auth + Source Config）

- 必填凭证：
- 必填定位参数（如 `Feishu Links` / `space_id`）：
- 可选参数（如 `max_folder_depth`）：
- 输入交互建议（强烈推荐）：
  - 优先让用户输入“业务链接”而不是底层 token
  - 支持批量输入（空格/逗号/分号/换行）
  - 前端实时显示：`X accepted, Y invalid`
  - 提交前阻断 invalid 输入，避免创建后才失败

### 3.2 鉴权流程

1. 凭证换 token（或 OAuth 回调拿 token）
2. 调用资源 API 验证可访问性（validate）
3. token 过期自动刷新/重取

### 3.3 入口解析与抽象（建议标准化）

- 抽象通用批量解析基类（如 `BatchEntryResolver`）：
  - 负责拆分、去重、无效项收集
  - 产出标准化入口列表
- 平台侧仅实现 `resolve_one()`：
  - 处理平台特有链接格式与对象类型映射
  - 例如：Folder / Wiki / Docx 的差异收敛
- 前端也采用插件式扩展：
  - 通用配置页保持轻量
  - 平台特化逻辑放在独立 extension 脚本

### 3.4 常见鉴权错误映射

- 401：凭证错误/过期
- 403：权限未开通或资源未授权
- 429：频控
- 400：参数错误（常见于链接/token 解析后未标准化）

## 4) Airweave 代码接入清单（实施步骤）

按下面顺序完成，避免“能创建连接但不能同步/搜索”的断层：

1. 新增 `AuthConfig`
   - `backend/airweave/platform/configs/auth.py`
2. 新增 `SourceConfig`
   - `backend/airweave/platform/configs/config.py`
3. 新增实体定义（Entity）
   - `backend/airweave/platform/entities/<platform>.py`
4. 注册实体映射
   - `backend/airweave/platform/entities/__init__.py` 的 `ENTITIES_BY_SOURCE`
5. 新增 Source 实现
   - `backend/airweave/platform/sources/<platform>.py`
6. 注册 Source
   - `backend/airweave/platform/sources/__init__.py` 的 `ALL_SOURCES`
7. 补齐搜索元数据描述（关键，避免 classic search 500）
   - `backend/airweave/domains/search/builders/collection_metadata.py` 的 `_SOURCE_DESCRIPTIONS`
8. 前端图标与来源展示
   - `frontend/src/components/icons/apps/<platform>.svg`
9. 前端配置表单校验（如有新增字段）
   - `frontend/src/components/shared/views/panel/SourceConfigView.tsx`
10. 前端平台特化扩展（推荐）
   - `frontend/src/components/shared/views/panel/source-config-extensions/<platform>.ts`
11. 后端入口解析器（推荐）
   - `backend/airweave/platform/sources/resolvers/<platform>.py`

## 5) 联调验证流程（建议一次走通）

### 5.1 创建连接阶段

- [ ] 在 UI 创建连接
- [ ] validate 成功
- [ ] 权限不足时错误信息可读（不是笼统 500）

### 5.2 同步阶段

- [ ] 触发 run sync 成功
- [ ] 至少插入 1 条实体（`entities_inserted > 0`）
- [ ] worker 日志无 `Source not found: <platform>`
- [ ] UI 状态与 `sync_job` 最终状态一致（避免“看起来 pending，实际 failed”）

### 5.3 搜索阶段

- [ ] 经典搜索/classic search 可返回结果
- [ ] 不出现 `No description found for source: <platform>`
- [ ] 结果可命中新增平台实体

## 6) 上线与运行保障

### 6.1 发布前检查

- [ ] backend/worker 已重启并加载新代码
- [ ] 前端 `dist` 已更新，图标与表单已生效
- [ ] 文档已补充“配置方式 + 常见问题”
- [ ] 容器分工已确认（API 与真正执行同步的 worker 不是同一进程）

### 6.2 监控与日志

- 关键日志字段：`source_short_name`、`request_id`、`sync_job_id`
- 关键指标：validate 成功率、同步成功率、429 比例、平均延迟

## 7) TODO 增强（统一结构）

- [ ] 增量同步（游标：`updated_time` / 变更事件）
- [ ] 删除检测（软删/硬删）
- [ ] ACL 映射（用户/部门/群组可见性）
- [ ] 接口级限流与重试退避
- [ ] 富媒体与附件解析

## 8) 遇到问题与排障记录（强制沉淀）

每个问题用固定格式记录：

- 现象：
- 根因：
- 定位方法（日志/API/代码）：
- 处理步骤：
- 预防动作（代码或文档）：

建议至少沉淀以下常见问题：
- 权限码 403（scope 不足 vs 资源不可见）
- Source 未注册（worker 未加载新代码）
- 搜索元数据未补全（description 缺失）
- 前端变更未生效（构建产物/缓存/权限问题）
- UI 卡 pending（前端展示未刷新 vs 后端任务已失败）
- 参数错误 400（链接输入未标准化，传入错误 token 形态）
