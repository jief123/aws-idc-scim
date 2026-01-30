# AWS Identity Center SCIM 用户和组同步工具

通过 SCIM API 将用户和组从 JSON 文件单向同步到 AWS Identity Center (IDC)。

## 架构

- `scim_service.py` - 核心服务层，封装所有 SCIM 操作
- `scim_cli.py` - 命令行接口
- `scim_api.py` - REST API 接口 (FastAPI)

## 安装

```bash
pip install -r requirements.txt
```

## 配置

### scim-config.json

```json
{
  "scim_endpoint": "https://scim.us-east-1.amazonaws.com/{tenant_id}/scim/v2",
  "scim_token": "your-scim-token"
}
```

从 AWS IAM Identity Center 控制台获取 SCIM endpoint 和 token。

### users.json

```json
[
  {
    "userName": "user@example.com",
    "name": { "familyName": "姓", "givenName": "名" },
    "displayName": "显示名称",
    "emails": [{ "value": "user@example.com", "type": "work", "primary": true }],
    "active": true,
    "title": "软件工程师",
    "department": "后端组"
  }
]
```

### groups.json

```json
[
  {
    "displayName": "开发组",
    "members": [{ "value": "user@example.com" }]
  }
]
```

## CLI 使用

### 用户管理

```bash
# 列出用户
python scim_cli.py user list
python scim_cli.py user list --format json

# 获取单个用户
python scim_cli.py user get <username>

# 创建/更新/删除用户
python scim_cli.py user create <file.json>
python scim_cli.py user update <file.json>
python scim_cli.py user delete <username>

# 增量同步 - 只添加/更新，不删除
python scim_cli.py user sync [users.json]
python scim_cli.py user sync --dry-run

# 全量同步 - 添加/更新（不删除）
python scim_cli.py user full-sync [users.json]

# 全量同步 - 添加/更新/删除
python scim_cli.py user full-sync --delete [users.json]
```

### 组管理

```bash
# 列出组
python scim_cli.py group list

# 创建/删除组
python scim_cli.py group create <group_name>
python scim_cli.py group delete <group_name>

# 成员管理
python scim_cli.py group list-members <group_name>
python scim_cli.py group add-member <group_name> <username>
python scim_cli.py group remove-member <group_name> <username>

# 从 CSV 导入成员到 groups.json
python scim_cli.py group import-csv members.csv

# 增量同步 - 只添加成员，不移除
python scim_cli.py group sync [groups.json]
python scim_cli.py group sync --dry-run

# 全量同步 - 添加/移除成员（不删除组）
python scim_cli.py group full-sync [groups.json]

# 全量同步 - 添加/移除成员，删除多余组
python scim_cli.py group full-sync --delete [groups.json]
```

## REST API

启动服务：

```bash
python scim_api.py
# 或
uvicorn scim_api:app --reload
```

### 用户 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /users | 列出所有用户 |
| GET | /users/{user_name} | 获取单个用户 |
| POST | /users | 创建用户 |
| PUT | /users/{user_name} | 更新用户 |
| DELETE | /users/{user_name} | 删除用户 |
| POST | /users/sync | 增量同步（只添加/更新） |
| POST | /users/full-sync | 全量同步（添加/更新/删除） |
| POST | /users/batch | 批量创建 |
| PUT | /users/batch | 批量更新 |
| DELETE | /users/batch | 批量删除 |

### 组 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /groups | 列出所有组 |
| POST | /groups | 创建组 |
| DELETE | /groups/{group_name} | 删除组 |
| GET | /groups/{group_name}/members | 列出组成员 |
| POST | /groups/{group_name}/members | 添加成员 |
| DELETE | /groups/{group_name}/members/{user_name} | 移除成员 |
| POST | /groups/{group_name}/members/batch | 批量添加成员 |
| DELETE | /groups/{group_name}/members/batch | 批量移除成员 |
| POST | /groups/sync | 增量同步（只添加成员） |
| POST | /groups/full-sync | 全量同步（添加/移除成员，删除组） |

### 同步请求格式

```json
{
  "data": [...],
  "dryRun": false,
  "delete": false
}
```

### 批量操作格式

用户批量操作使用 users.json 格式：
```json
[{"userName": "...", "displayName": "...", ...}]
```

成员批量操作使用 groups.json 中 members 格式：
```json
{"members": [{"value": "username1"}, {"value": "username2"}]}
```

## 同步模式说明

| 操作 | sync | full-sync | full-sync --delete |
|------|------|-----------|-------------------|
| 创建用户/组 | ✓ | ✓ | ✓ |
| 更新用户 | ✓ | ✓ | ✓ |
| 添加组成员 | ✓ | ✓ | ✓ |
| 移除组成员 | ✗ | ✓ | ✓ |
| 删除用户 | ✗ | ✗ | ✓ |
| 删除组 | ✗ | ✗ | ✓ |

## 输出符号

| 符号 | 含义 |
|------|------|
| + | 创建 |
| ↻ | 更新 |
| - | 删除 |
| ○ | 无变化 |
| ✗ | 错误 |

## AWS IDC SCIM 限制

AWS IDC 的 SCIM 实现与标准 SCIM 2.0 有一些差异，详见 [官方文档](https://docs.aws.amazon.com/singlesignon/latest/developerguide/limitations.html)。

### SCIM 标准限制

| 限制 | 说明 |
|------|------|
| 多值属性只支持单值 | emails/phoneNumbers/addresses 只能有一个值 |
| GET /Groups 不返回成员 | 需用 filter `members.value eq "{userId}"` 查询 |
| PUT Group 不支持 | 返回 501 Not Implemented，只能用 PATCH add/remove 操作成员 |
| PATCH Group 不支持 replace/remove all | 只能用 add/remove 操作|
| PUT User 要求 body 包含 id | SCIM 标准规定 `id` 是 readOnly 属性，PUT 时应忽略；但 IDC 要求必须包含且匹配 URL 中的 id，否则返回 400（未明确文档化，仅在[示例](https://docs.aws.amazon.com/singlesignon/latest/developerguide/putuser.html)中体现）。本工具使用 PATCH 代替 |
| Filter 操作符受限 | 只支持 `eq` 和 `and`，不支持 `co`/`sw`/`or` 等 |
| 不支持的 User 属性 | password, ims, photos, groups, entitlements, x509Certificates |

### API 限制

| 限制 | 说明 |
|------|------|
| 单次成员操作上限 | 最多添加/移除 100 个成员 |
| 不能清空成员 | 不能一次删除所有成员（空列表） |
| 请求频率限制 | 超限返回 429 ThrottlingException |

### 性能说明

以下操作需要遍历所有用户来获取组成员关系，API 调用次数 = 用户数量 N：

- `group list-members` - 列出组成员
- `group sync` / `group full-sync` - 同步组成员

如需更高效的查询，可考虑使用 AWS Identity Store API 的 `ListGroupMemberships`（每组 1 次调用）。

## 注意事项

- `scim-config.json` 包含敏感信息，已添加到 `.gitignore`
- 建议先用 `--dry-run` 预览再执行
- `--delete` 会删除 IDC 中多余的用户/组，请谨慎使用
- 组成员使用 userName 引用，必须先同步用户再同步组
- SCIM token 有效期一年，注意续期
