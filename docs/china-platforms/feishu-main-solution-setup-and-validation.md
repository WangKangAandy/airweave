# 飞书文档接入主方案（DIRECT）配置与验证指南

> 目标：用 Airweave 接入飞书文档，采用主方案 `app_id + app_secret + folder_token`，并通过“测试文档同步”验证可行性。

## 一句话结论

对于 Airweave 这类“服务端持续同步”场景，主方案应采用 **DIRECT 模式**：

- 凭证：`app_id` + `app_secret`
- 范围：`folder_token` 指定目录
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

## 3. 获取 `folder_token`

建议在飞书中创建一个测试目录，例如：`Airweave-Feishu-Test`。  
进入该目录后，从链接中提取 `folder_token`（通常是 URL 里的目录标识）。

参考下图（按图中步骤进入目录分享并复制链接）：

飞书 folder_token 获取示意图

提取方式示例：

- 目录链接形如：`https://my.feishu.cn/drive/folder/<folder_token>?...`
- 其中 `folder/` 后到 `?` 前的字符串即 `folder_token`
- （TODO： 后面可考虑不用手动提取， 后台自动提取）

---

## 4. Airweave 配置（主方案）

在 Airweave 前端：

1. 选择 `Feishu` source
2. 认证方式选 DIRECT
3. 填入：
  - `app_id`
  - `app_secret`
4. 配置项填入：
  - `folder_token`
  - `max_folder_depth`（建议先填 `2` 或 `3`）
5. 创建连接并触发首次同步

---

## 5. 用“测试文档”验证同步是否可行

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

## 6. 常见失败与排查

### 1) `tenant_access_token` 获取失败

常见原因：

- `app_id` / `app_secret` 错误
- 应用未安装到目标租户
- 应用状态异常（未启用）

### 2) 连接创建成功但拉不到文档

常见原因：

- `folder_token` 填错
- 目录下没有 `docx` 文档
- 文档权限对应用不可见

### 3) 同步成功但检索不到

常见原因：

- 文档内容为空或仅图片
- 同步后索引尚未完成（可稍等重试）

---

## 7. 建议的生产化增强（后续）

- 增量同步（按 `modified_time`）
- 删除检测（目录移除、文档删除）
- 更细粒度限流（按接口配额）
- ACL 映射（文档可见性）

---

## 8. 当前结论

`app_id/app_secret + folder_token` 作为飞书接入主方案是可行且合理的。  
若你需要“用户授权体验”，可以额外提供 OAuth 模式，但不建议替代主方案。