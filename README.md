# AWS Identity Center SCIM CLI

通过 SCIM API 管理 AWS Identity Center (IDC) 的用户和组。

## 特性

- 自定义 SCIM 客户端库 (`aws_idc_scim`)，专门处理 AWS IDC 的 SCIM 实现限制
- 命令行工具 (`scim_cli.py`) 支持用户/组的 CRUD 和同步操作
- REST API 服务 (`scim_api.py`) 基于 FastAPI
- 支持增量同步和全量同步

## 架构

```
aws_idc_scim/          # 核心 SCIM 客户端库
├── models.py          # 数据模型 (SCIMUser, SCIMGroup, etc.)
├── client.py          # HTTP 客户端，处理 AWS IDC 特有行为
├── filters.py         # SCIM Filter 构建器
└── __init__.py

scim_cli.py            # 命令行接口
scim_api.py            # REST API 接口 (FastAPI)
```

## 安装

```bash
pip install -r requirements.txt
```

依赖：
- `httpx` - HTTP 客户端
- `fastapi` + `uvicorn` - REST API (可选)

## 配置

复制示例配置文件：

```bash
cp scim-config.example.json scim-config.json
```

编辑 `scim-config.json`：

```json
{
  "scim_endpoint": "https://scim.us-east-1.amazonaws.com/{tenant_id}/scim/v2",
  "scim_token": "your-scim-token"
}
```

从 AWS IAM Identity Center 控制台 → Settings → Automatic provisioning 获取 SCIM endpoint 和 token。

## 数据文件格式

### users.json

```json
[
  {
    "userName": "user@example.com",
    "displayName": "User Name",
    "name": { "familyName": "Name", "givenName": "User" },
    "emails": [{ "value": "user@example.com", "type": "work", "primary": true }],
    "active": true
  }
]
```

### groups.json

```json
[
  {
    "displayName": "Developers",
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

# 增量同步 (只添加/更新，不删除)
python scim_cli.py user sync [users.json]
python scim_cli.py user sync --dry-run

# 全量同步 (添加/更新，可选删除)
python scim_cli.py user full-sync [users.json]
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

# 从 CSV 导入
python scim_cli.py group import-csv members.csv

# 增量同步 (只添加成员)
python scim_cli.py group sync [groups.json]

# 全量同步 (添加/移除成员，可选删除组)
python scim_cli.py group full-sync [groups.json]
python scim_cli.py group full-sync --delete [groups.json]
```

## 同步模式

| 操作 | sync | full-sync | full-sync --delete |
|------|:----:|:---------:|:------------------:|
| 创建用户/组 | ✓ | ✓ | ✓ |
| 更新用户 | ✓ | ✓ | ✓ |
| 添加组成员 | ✓ | ✓ | ✓ |
| 移除组成员 | ✗ | ✓ | ✓ |
| 删除用户 | ✗ | ✗ | ✓ |
| 删除组 | ✗ | ✗ | ✓ |

## 账单 CSV 用户名转换

`convert_kiro_csv.py` 可以将 Kiro 账单 CSV 中的 Identity Store ARN（`arn:aws:identitystore:::user/xxx`）自动替换为对应的 SCIM 用户名。

- 不依赖固定表头，自动扫描所有单元格匹配 ARN 格式
- 同一 user_id 只查询一次 SCIM API（有缓存）
- CSV 其他列原样保留

```bash
# 默认处理 kiro_bill_parsed.csv
python convert_kiro_csv.py

# 指定其他 CSV 文件
python convert_kiro_csv.py my_bill.csv
```

## REST API

```bash
python scim_api.py
# 或
uvicorn scim_api:app --reload --port 8000
```

API 文档: http://localhost:8000/docs

## 使用 aws_idc_scim 库

```python
from aws_idc_scim import SCIMClient, SCIMUser, SCIMName, SCIMEmail, SCIMGroup

# 创建客户端
client = SCIMClient(
    endpoint="https://scim.us-east-1.amazonaws.com/xxx/scim/v2",
    token="your-token"
)

# 列出用户
for user in client.list_users():
    print(f"{user.userName} ({user.displayName})")

# 创建用户
new_user = SCIMUser(
    userName="new@example.com",
    displayName="New User",
    name=SCIMName(familyName="User", givenName="New"),
    emails=[SCIMEmail(value="new@example.com")],
)
created = client.create_user(new_user)

# 同步用户
users = [SCIMUser(...), SCIMUser(...)]
result = client.sync_users(users, dry_run=False)
print(f"Created: {result.created}, Updated: {result.updated}")

# 组操作
client.add_group_members(group_id, [user_id1, user_id2])
groups = client.get_user_groups(user_id)

client.close()
```

## AWS IDC SCIM 限制

本库专门处理 AWS IDC 的 SCIM 实现限制：

| 限制 | 处理方式 |
|------|----------|
| 多值属性只支持单值 | emails/phoneNumbers/addresses 设计为单值 |
| GET /Groups 不返回成员 | 提供 `list_group_members()` 遍历查询 |
| PUT Group 不支持 (501) | 使用 PATCH add/remove 操作成员 |
| PUT User 要求 body 包含 id | `update_user()` 自动包含 id |
| Filter 只支持 eq 和 and | `Filter` 构建器只提供支持的操作 |
| 分页最大 100 | 自动处理分页 |
| 不支持的属性 | password, ims, photos, groups, entitlements, x509Certificates |

详见 [AWS 官方文档](https://docs.aws.amazon.com/singlesignon/latest/developerguide/limitations.html)

## 输出符号

| 符号 | 含义 |
|------|------|
| + | 创建 |
| ↻ | 更新 |
| - | 删除 |
| ○ | 无变化 |
| ✗ | 错误 |

## 注意事项

- `scim-config.json` 包含敏感 token，已在 `.gitignore` 中排除
- 建议先用 `--dry-run` 预览再执行
- `--delete` 会删除 IDC 中多余的用户/组，请谨慎使用
- 组成员使用 userName 引用，必须先同步用户再同步组
- SCIM token 有效期一年，注意续期

## License

MIT
