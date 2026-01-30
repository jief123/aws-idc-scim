# AWS IDC SCIM Client

专为 AWS Identity Center SCIM 实现设计的 Python 客户端。

## 安装依赖

```bash
pip install httpx
```

## 快速开始

```python
from aws_idc_scim import SCIMClient, SCIMUser, SCIMName, SCIMEmail, Filter

# 创建客户端
client = SCIMClient(
    endpoint="https://scim.us-east-1.amazonaws.com/xxx/scim/v2",
    token="your-scim-token"
)

# 列出所有用户
for user in client.list_users():
    print(f"{user.userName} ({user.displayName})")

# 按用户名查找
user = client.find_user_by_username("test@example.com")

# 创建用户
new_user = SCIMUser(
    userName="new@example.com",
    displayName="New User",
    name=SCIMName(familyName="User", givenName="New"),
    emails=[SCIMEmail(value="new@example.com")],
)
created = client.create_user(new_user)
print(f"Created: {created.id}")

# 使用 Filter 构建器
filter = Filter.user_name("test@example.com")
# 或组合条件
filter = Filter.display_name("Test") & Filter.active(True)
users = client.get_all_users(str(filter))

# 组成员操作
client.add_group_members(group_id, ["user-id-1", "user-id-2"])
client.remove_group_members(group_id, ["user-id-3"])

# 查询用户所属的组
groups = client.get_user_groups(user_id)

# 关闭连接
client.close()

# 或使用 context manager
with SCIMClient(endpoint, token) as client:
    users = client.get_all_users()
```

## AWS IDC SCIM 限制

此客户端专门处理 AWS IDC 的 SCIM 实现限制：

| 限制 | 处理方式 |
|------|----------|
| 多值属性只支持单值 | emails/phoneNumbers/addresses 设计为单值 |
| GET /Groups 不返回成员 | 提供 `get_user_groups()` 和 `is_user_in_group()` |
| PUT Group 不支持 | 使用 PATCH add/remove 操作成员 |
| PUT User 要求 body 包含 id | `update_user()` 自动包含 id |
| Filter 只支持 eq 和 and | `Filter` 构建器只提供支持的操作 |
| 分页最大 100 | 自动处理分页，提供迭代器接口 |
| 单次成员操作最多 100 | `add/remove_group_members()` 自动分批 |

## 数据模型

所有数据模型严格按照 [AWS IDC SCIM 文档](https://docs.aws.amazon.com/singlesignon/latest/developerguide/limitations.html) 定义。

### User 单值属性

| 属性 | 子属性 | 支持 |
|------|--------|------|
| userName | | ✓ |
| name | formatted, familyName, givenName, middleName, honorificPrefix, honorificSuffix | ✓ |
| displayName | | ✓ |
| nickName | | ✓ |
| profileUrl | | ✓ |
| title | | ✓ |
| userType | | ✓ |
| preferredLanguage | | ✓ |
| locale | | ✓ |
| timezone | | ✓ |
| active | | ✓ |
| password | | ✗ |

### User 多值属性 (只支持单值)

| 属性 | 子属性 | 支持 |
|------|--------|------|
| emails | value, type, primary | ✓ (display 不支持) |
| phoneNumbers | value, type | ✓ (display 不支持) |
| addresses | formatted, streetAddress, locality, region, postalCode, country | ✓ |
| roles | value, type, primary | ✓ |
| ims, photos, groups, entitlements, x509Certificates | | ✗ |

### Enterprise User 扩展

| 属性 | 子属性 | 支持 |
|------|--------|------|
| employeeNumber | | ✓ |
| costCenter | | ✓ |
| organization | | ✓ |
| division | | ✓ |
| department | | ✓ |
| manager | value, $ref | ✓ (displayName 不支持) |

### Group 属性

| 属性 | 子属性 | 支持 |
|------|--------|------|
| displayName | | ✓ |
| members | value, type, $ref | ✓ (display 不支持, GET 不返回) |

## API 参考

### SCIMClient

- `list_users(filter)` - 迭代所有用户
- `get_all_users(filter)` - 获取所有用户列表
- `get_user(user_id)` - 获取单个用户
- `find_user_by_username(username)` - 按用户名查找
- `create_user(user)` - 创建用户
- `update_user(user)` - 更新用户 (PUT)
- `patch_user(user_id, operations)` - 部分更新 (PATCH)
- `delete_user(user_id)` - 删除用户
- `list_groups(filter)` - 迭代所有组
- `get_all_groups(filter)` - 获取所有组列表
- `get_group(group_id)` - 获取单个组
- `find_group_by_name(name)` - 按名称查找组
- `create_group(group)` - 创建组
- `delete_group(group_id)` - 删除组
- `add_group_members(group_id, user_ids)` - 添加成员
- `remove_group_members(group_id, user_ids)` - 移除成员
- `is_user_in_group(group_id, user_id)` - 检查成员关系
- `get_user_groups(user_id)` - 获取用户所属的组

### Filter

```python
Filter.eq("attr", "value")      # attr eq "value"
Filter.user_name("email")       # userName eq "email"
Filter.display_name("name")     # displayName eq "name"
Filter.external_id("id")        # externalId eq "id"
Filter.active(True)             # active eq true
Filter.member_eq("userId")      # members.value eq "userId"

# 组合
f1 & f2                         # (f1) and (f2)
```

## 注意事项

- 所有可选字段在序列化时只包含有值的字段，不会发送 `null` 值（AWS IDC 不接受）
- `to_dict()` 方法会自动过滤 `None` 值
- `from_dict()` 方法会正确处理 API 响应中缺失的字段
