# 飞书文档接入方案

## 接入目标

- 支持通过飞书开放平台应用凭证创建 Source Connection
- 以 `folder_token` 为起点同步文档
- 首期支持 `docx` 文本正文，满足检索可用

## 鉴权与配置

### 凭证字段

- `app_id`
- `app_secret`
- `folder_token`
- `max_folder_depth`（可选）

### 鉴权流程

1. 调用 `tenant_access_token/internal` 换取 `tenant_access_token`
2. 访问 Drive / Docx 接口时使用 `Bearer token`
3. token 过期后自动重换

## 接口适配内容

### 文件发现

- `drive/v1/files`：按 folder 遍历，递归进入子目录

### 内容拉取

- `docx/v1/documents/{token}`：获取标题/元信息
- `docx/v1/documents/{token}/raw_content`：获取正文文本

### 实体映射（MVP）

- `FeishuDocxEntity`
  - 主键：`doc_token`
  - 关键字段：`title`、`raw_content`、`url`、`created_time`、`updated_time`

## TODO 增强

- [ ] 增量同步（基于 `modified_time` 游标）
- [ ] 删除检测（目录与文档删除事件）
- [ ] Wiki 节点支持（space/wiki tree）
- [ ] 富媒体支持（图片、表格、附件）
- [ ] ACL 权限建模（用户/部门可见性）
- [ ] 更细粒度限流器（按接口配额分桶）

## 遇到的问题与风险

- `raw_content` 接口频控较敏感，需要严格限流
- 企业内权限模型复杂，应用权限 + 资源权限双层校验
- 文档类型存在差异（doc/docx/wiki/sheet），MVP 仅覆盖 docx

## 验证清单

- [ ] 能创建连接并通过 validate
- [ ] 能拉到至少 1 篇 docx 正文
- [ ] 能完成一次全量同步并被搜索命中
- [ ] token 过期后可自动恢复
