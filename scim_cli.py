#!/usr/bin/env python3
"""
AWS Identity Center SCIM CLI
"""
import argparse
import json
import sys
from pathlib import Path

from aws_idc_scim import (
    SCIMClient,
    SCIMClientError,
    SCIMUser,
    SCIMGroup,
    SCIMName,
    SCIMEmail,
    SCIMValidationError,
    PatchOperation,
)


def load_json(file: str) -> dict | list:
    path = Path(file)
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_client() -> SCIMClient:
    config = load_json("scim-config.json")
    if not config or not isinstance(config, dict):
        print("错误: scim-config.json 不存在或格式错误")
        sys.exit(1)
    return SCIMClient(config["scim_endpoint"], config["scim_token"])


def build_user(data: dict) -> SCIMUser:
    """从 dict 构建 SCIMUser"""
    name = None
    if data.get("name"):
        name = SCIMName(
            familyName=data["name"].get("familyName"),
            givenName=data["name"].get("givenName"),
        )
    
    emails = None
    if data.get("emails"):
        emails = [SCIMEmail(
            value=e["value"],
            type=e.get("type"),
            primary=e.get("primary"),
        ) for e in data["emails"]]
    
    return SCIMUser(
        userName=data["userName"],
        displayName=data.get("displayName"),
        name=name,
        emails=emails,
        active=data.get("active"),
        title=data.get("title"),
        userType=data.get("userType"),
        externalId=data.get("externalId"),
    )


def user_to_dict(user: SCIMUser) -> dict:
    """SCIMUser 转 dict"""
    d = user.to_dict()
    d["id"] = user.id
    return d


# ========== 用户命令 ==========

def cmd_user_list(args):
    client = get_client()
    users = client.get_all_users()
    if args.format == "json":
        print(json.dumps([user_to_dict(u) for u in users], indent=2, ensure_ascii=False))
    else:
        print(f"共 {len(users)} 个用户:\n")
        for u in users:
            status = "✓" if u.active else "✗"
            print(f"  {status} {u.userName} ({u.displayName}) [id: {u.id}]")
    client.close()


def cmd_user_get(args):
    client = get_client()
    user = client.find_user_by_username(args.username)
    if not user:
        print(f"用户不存在: {args.username}")
        client.close()
        return 1
    print(json.dumps(user_to_dict(user), indent=2, ensure_ascii=False))
    client.close()


def cmd_user_create(args):
    client = get_client()
    data = load_json(args.file)
    users = data if isinstance(data, list) else [data]
    has_error = False
    for u in users:
        try:
            user = build_user(u)
            result = client.create_user(user)
            print(f"✓ 创建: {result.userName} [id: {result.id}]")
        except (SCIMClientError, SCIMValidationError) as e:
            print(f"✗ {u.get('userName', '?')}: {e}")
            has_error = True
    client.close()
    return 1 if has_error else 0


def cmd_user_update(args):
    client = get_client()
    data = load_json(args.file)
    users = data if isinstance(data, list) else [data]
    has_error = False
    for u in users:
        try:
            name = u.get("userName", "")
            existing = client.find_user_by_username(name)
            if not existing or not existing.id:
                raise ValueError(f"用户不存在: {name}")
            
            user = build_user(u)
            user_dict = user.to_dict()
            
            operations = []
            for key, value in user_dict.items():
                if key not in ("id", "schemas", "meta"):
                    operations.append(PatchOperation(op="replace", path=key, value=value))
            
            client.patch_user(existing.id, operations)
            print(f"✓ 更新: {name}")
        except (SCIMClientError, SCIMValidationError, ValueError) as e:
            print(f"✗ {u.get('userName', '?')}: {e}")
            has_error = True
    client.close()
    return 1 if has_error else 0


def cmd_user_delete(args):
    client = get_client()
    try:
        user = client.find_user_by_username(args.username)
        if not user or not user.id:
            raise ValueError(f"用户不存在: {args.username}")
        client.delete_user(user.id)
        print(f"✓ 删除: {args.username}")
        client.close()
        return 0
    except (SCIMClientError, ValueError) as e:
        print(f"✗ {e}")
        client.close()
        return 1


def cmd_user_sync(args):
    client = get_client()
    data = load_json(args.file)
    local_users = data if isinstance(data, list) else [data]
    print(f"增量同步 {len(local_users)} 个本地用户（只添加/更新）...\n")
    
    users = [build_user(u) for u in local_users]
    result = client.sync_users(users, dry_run=args.dry_run)
    
    for name in result.unchanged:
        print(f"  ○ {name}")
    for name in result.created:
        detail = result.details.get(name, {})
        uid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  + {name} [id: {uid}]{suffix}")
    for name in result.updated:
        detail = result.details.get(name, {})
        uid = detail.get("id", "?")
        fields = detail.get("fields", [])
        suffix = " (预览)" if args.dry_run else ""
        print(f"  ↻ {name} [id: {uid}] 变更: {', '.join(fields)}{suffix}")
    for err in result.errors:
        print(f"  ✗ {err}")
    
    print(f"\n创建:{len(result.created)} 更新:{len(result.updated)} 无变化:{len(result.unchanged)} 错误:{len(result.errors)}")
    client.close()


def cmd_user_full_sync(args):
    client = get_client()
    data = load_json(args.file)
    local_users = data if isinstance(data, list) else [data]
    mode = "添加/更新/删除" if args.delete else "添加/更新"
    print(f"全量同步 {len(local_users)} 个本地用户（{mode}）...\n")
    
    users = [build_user(u) for u in local_users]
    result = client.full_sync_users(users, allow_delete=args.delete, dry_run=args.dry_run)
    
    for name in result.unchanged:
        print(f"  ○ {name}")
    for name in result.created:
        detail = result.details.get(name, {})
        uid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  + {name} [id: {uid}]{suffix}")
    for name in result.updated:
        detail = result.details.get(name, {})
        uid = detail.get("id", "?")
        fields = detail.get("fields", [])
        suffix = " (预览)" if args.dry_run else ""
        print(f"  ↻ {name} [id: {uid}] 变更: {', '.join(fields)}{suffix}")
    for name in result.deleted:
        detail = result.details.get(name, {})
        uid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  - {name} [id: {uid}]{suffix}")
    for err in result.errors:
        print(f"  ✗ {err}")
    
    summary = f"创建:{len(result.created)} 更新:{len(result.updated)} 无变化:{len(result.unchanged)} 错误:{len(result.errors)}"
    if args.delete:
        summary = f"创建:{len(result.created)} 更新:{len(result.updated)} 删除:{len(result.deleted)} 无变化:{len(result.unchanged)} 错误:{len(result.errors)}"
    print(f"\n{summary}")
    client.close()


# ========== 组命令 ==========

def cmd_group_list(args):
    client = get_client()
    groups = client.get_all_groups()
    print(f"共 {len(groups)} 个组:\n")
    for g in groups:
        print(f"  {g.displayName} [id: {g.id}]")
    client.close()


def cmd_group_create(args):
    client = get_client()
    try:
        result = client.create_group(SCIMGroup(displayName=args.group_name))
        print(f"✓ 创建: {result.displayName} [id: {result.id}]")
        client.close()
        return 0
    except SCIMClientError as e:
        print(f"✗ {e}")
        client.close()
        return 1


def cmd_group_delete(args):
    client = get_client()
    try:
        group = client.find_group_by_name(args.group_name)
        if not group or not group.id:
            raise ValueError(f"组不存在: {args.group_name}")
        client.delete_group(group.id)
        print(f"✓ 删除: {args.group_name}")
        client.close()
        return 0
    except (SCIMClientError, ValueError) as e:
        print(f"✗ {e}")
        client.close()
        return 1


def cmd_group_list_members(args):
    client = get_client()
    try:
        group = client.find_group_by_name(args.group_name)
        if not group or not group.id:
            raise ValueError(f"组不存在: {args.group_name}")
        
        members = client.list_group_members(group.id)
        print(f"组 '{args.group_name}' 有 {len(members)} 个成员:\n")
        for m in members:
            print(f"  {m.userName} ({m.displayName}) [id: {m.id}]")
        client.close()
        return 0
    except (SCIMClientError, ValueError) as e:
        print(f"✗ {e}")
        client.close()
        return 1


def cmd_group_add_member(args):
    client = get_client()
    try:
        group = client.find_group_by_name(args.group)
        if not group or not group.id:
            raise ValueError(f"组不存在: {args.group}")
        
        user = client.find_user_by_username(args.user)
        if not user or not user.id:
            raise ValueError(f"用户不存在: {args.user}")
        
        client.add_group_members(group.id, [user.id])
        print(f"✓ 添加 {args.user} [id: {user.id}] 到 {args.group}")
        client.close()
        return 0
    except (SCIMClientError, ValueError) as e:
        print(f"✗ {e}")
        client.close()
        return 1


def cmd_group_remove_member(args):
    client = get_client()
    try:
        group = client.find_group_by_name(args.group)
        if not group or not group.id:
            raise ValueError(f"组不存在: {args.group}")
        
        user = client.find_user_by_username(args.user)
        if not user or not user.id:
            raise ValueError(f"用户不存在: {args.user}")
        
        client.remove_group_members(group.id, [user.id])
        print(f"✓ 从 {args.group} 移除 {args.user}")
        client.close()
        return 0
    except (SCIMClientError, ValueError) as e:
        print(f"✗ {e}")
        client.close()
        return 1



def cmd_group_sync(args):
    client = get_client()
    data = load_json(args.file)
    local_groups = data if isinstance(data, list) else [data]
    print(f"增量同步 {len(local_groups)} 个本地组（只添加成员）...\n")
    
    # 构建 groups 和 members_map
    groups = []
    members_map = {}
    for g in local_groups:
        name = g["displayName"]
        groups.append(SCIMGroup(displayName=name))
        members = []
        for m in g.get("members", []):
            member_name = m.get("value") if isinstance(m, dict) else m
            if member_name:
                members.append(member_name)
        members_map[name] = members
    
    result = client.sync_groups(groups, members_map, dry_run=args.dry_run)
    
    for name in result.unchanged:
        detail = result.details.get(name, {})
        print(f"  ○ {name}")
        for m in detail.get("skipped", []):
            print(f"      ⚠ 跳过成员(用户不存在): {m}")
    for name in result.created:
        detail = result.details.get(name, {})
        gid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  + {name} [id: {gid}]{suffix}")
        for m in detail.get("added", []):
            print(f"      添加成员: {m['userName']} [id: {m['id']}]")
        for m in detail.get("skipped", []):
            print(f"      ⚠ 跳过成员(用户不存在): {m}")
    for name in result.updated:
        detail = result.details.get(name, {})
        gid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  ↻ {name} [id: {gid}]{suffix}")
        for m in detail.get("added", []):
            print(f"      添加成员: {m['userName']} [id: {m['id']}]")
        for m in detail.get("skipped", []):
            print(f"      ⚠ 跳过成员(用户不存在): {m}")
    for err in result.errors:
        print(f"  ✗ {err}")
    
    print(f"\n创建:{len(result.created)} 更新:{len(result.updated)} 无变化:{len(result.unchanged)} 错误:{len(result.errors)}")
    client.close()


def cmd_group_full_sync(args):
    client = get_client()
    data = load_json(args.file)
    local_groups = data if isinstance(data, list) else [data]
    mode = "添加/移除成员，删除多余组" if args.delete else "添加/移除成员"
    print(f"全量同步 {len(local_groups)} 个本地组（{mode}）...\n")
    
    # 构建 groups 和 members_map
    groups = []
    members_map = {}
    for g in local_groups:
        name = g["displayName"]
        groups.append(SCIMGroup(displayName=name))
        members = []
        for m in g.get("members", []):
            member_name = m.get("value") if isinstance(m, dict) else m
            if member_name:
                members.append(member_name)
        members_map[name] = members
    
    result = client.full_sync_groups(groups, members_map, allow_delete=args.delete, dry_run=args.dry_run)
    
    for name in result.unchanged:
        detail = result.details.get(name, {})
        print(f"  ○ {name}")
        for m in detail.get("skipped", []):
            print(f"      ⚠ 跳过成员(用户不存在): {m}")
    for name in result.created:
        detail = result.details.get(name, {})
        gid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  + {name} [id: {gid}]{suffix}")
        for m in detail.get("added", []):
            print(f"      添加成员: {m['userName']} [id: {m['id']}]")
        for m in detail.get("skipped", []):
            print(f"      ⚠ 跳过成员(用户不存在): {m}")
    for name in result.updated:
        detail = result.details.get(name, {})
        gid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  ↻ {name} [id: {gid}]{suffix}")
        for m in detail.get("added", []):
            print(f"      添加成员: {m['userName']} [id: {m['id']}]")
        for m in detail.get("removed", []):
            print(f"      移除成员: {m['userName']} [id: {m['id']}]")
        for m in detail.get("skipped", []):
            print(f"      ⚠ 跳过成员(用户不存在): {m}")
    for name in result.deleted:
        detail = result.details.get(name, {})
        gid = detail.get("id", "?")
        suffix = " (预览)" if args.dry_run else ""
        print(f"  - {name} [id: {gid}]{suffix}")
    for err in result.errors:
        print(f"  ✗ {err}")
    
    summary = f"创建:{len(result.created)} 更新:{len(result.updated)} 无变化:{len(result.unchanged)} 错误:{len(result.errors)}"
    if args.delete:
        summary = f"创建:{len(result.created)} 更新:{len(result.updated)} 删除:{len(result.deleted)} 无变化:{len(result.unchanged)} 错误:{len(result.errors)}"
    print(f"\n{summary}")
    client.close()


def cmd_group_import_csv(args):
    """从 CSV 生成/更新 groups.json"""
    import csv
    
    # 读取 CSV
    rows = []
    with open(args.file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = row.get('email') or row.get('Email') or row.get('EMAIL')
            group = row.get('group') or row.get('Group') or row.get('GROUP')
            if email and group:
                rows.append((email.strip(), group.strip()))
    
    if not rows:
        print("CSV 中没有有效数据（需要 email 和 group 列）")
        return 1
    
    # 读取现有 groups.json
    output_file = args.output
    existing = load_json(output_file)
    if not isinstance(existing, list):
        existing = []
    
    # 转成 dict 方便操作
    groups_map = {}
    for g in existing:
        name = g.get("displayName")
        members = {m.get("value") for m in g.get("members", [])}
        groups_map[name] = members
    
    # 合并 CSV 数据
    added_count = 0
    for email, group in rows:
        if group not in groups_map:
            groups_map[group] = set()
        if email not in groups_map[group]:
            groups_map[group].add(email)
            added_count += 1
    
    # 转回 JSON 格式
    result = []
    for name in sorted(groups_map.keys()):
        members = [{"value": m} for m in sorted(groups_map[name])]
        result.append({"displayName": name, "members": members})
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"从 CSV 读取 {len(rows)} 条记录")
    print(f"新增 {added_count} 个成员关系")
    print(f"共 {len(result)} 个组，已写入 {output_file}")
    print(f"\n下一步: python scim_cli.py group sync")


# ========== 主函数 ==========

def main():
    parser = argparse.ArgumentParser(prog='scim-cli', description='AWS IDC SCIM CLI')
    subparsers = parser.add_subparsers(dest='command', help='命令')
    
    # user 命令
    user_parser = subparsers.add_parser('user', help='用户管理')
    user_sub = user_parser.add_subparsers(dest='action')
    
    p = user_sub.add_parser('list', help='列出用户')
    p.add_argument('--format', choices=['table', 'json'], default='table')
    p.set_defaults(func=cmd_user_list)
    
    p = user_sub.add_parser('get', help='获取用户')
    p.add_argument('username')
    p.set_defaults(func=cmd_user_get)
    
    p = user_sub.add_parser('create', help='创建用户')
    p.add_argument('file', help='JSON 文件')
    p.set_defaults(func=cmd_user_create)
    
    p = user_sub.add_parser('update', help='更新用户')
    p.add_argument('file', help='JSON 文件')
    p.set_defaults(func=cmd_user_update)
    
    p = user_sub.add_parser('delete', help='删除用户')
    p.add_argument('username')
    p.set_defaults(func=cmd_user_delete)
    
    p = user_sub.add_parser('sync', help='增量同步用户（只添加/更新）')
    p.add_argument('file', nargs='?', default='users.json', help='JSON 文件')
    p.add_argument('--dry-run', action='store_true', help='预览模式')
    p.set_defaults(func=cmd_user_sync)
    
    p = user_sub.add_parser('full-sync', help='全量同步用户（添加/更新，可选删除）')
    p.add_argument('file', nargs='?', default='users.json', help='JSON 文件')
    p.add_argument('--dry-run', action='store_true', help='预览模式')
    p.add_argument('--delete', action='store_true', help='删除 IDC 中多余的用户')
    p.set_defaults(func=cmd_user_full_sync)
    
    # group 命令
    group_parser = subparsers.add_parser('group', help='组管理')
    group_sub = group_parser.add_subparsers(dest='action')
    
    p = group_sub.add_parser('list', help='列出组')
    p.set_defaults(func=cmd_group_list)
    
    p = group_sub.add_parser('create', help='创建组')
    p.add_argument('group_name')
    p.set_defaults(func=cmd_group_create)
    
    p = group_sub.add_parser('delete', help='删除组')
    p.add_argument('group_name')
    p.set_defaults(func=cmd_group_delete)
    
    p = group_sub.add_parser('list-members', help='列出组成员')
    p.add_argument('group_name')
    p.set_defaults(func=cmd_group_list_members)
    
    p = group_sub.add_parser('add-member', help='添加成员')
    p.add_argument('group')
    p.add_argument('user')
    p.set_defaults(func=cmd_group_add_member)
    
    p = group_sub.add_parser('remove-member', help='移除成员')
    p.add_argument('group')
    p.add_argument('user')
    p.set_defaults(func=cmd_group_remove_member)
    
    p = group_sub.add_parser('sync', help='增量同步组（只添加成员）')
    p.add_argument('file', nargs='?', default='groups.json', help='JSON 文件')
    p.add_argument('--dry-run', action='store_true', help='预览模式')
    p.set_defaults(func=cmd_group_sync)
    
    p = group_sub.add_parser('full-sync', help='全量同步组（添加/移除成员，可选删除组）')
    p.add_argument('file', nargs='?', default='groups.json', help='JSON 文件')
    p.add_argument('--dry-run', action='store_true', help='预览模式')
    p.add_argument('--delete', action='store_true', help='删除 IDC 中多余的组')
    p.set_defaults(func=cmd_group_full_sync)
    
    p = group_sub.add_parser('import-csv', help='从 CSV 生成/更新 groups.json')
    p.add_argument('file', help='CSV 文件（需要 email 和 group 列）')
    p.add_argument('-o', '--output', default='groups.json', help='输出文件，默认 groups.json')
    p.set_defaults(func=cmd_group_import_csv)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    if hasattr(args, 'func'):
        return args.func(args) or 0
    else:
        parser.parse_args([args.command, '-h'])
        return 0


if __name__ == "__main__":
    sys.exit(main())
