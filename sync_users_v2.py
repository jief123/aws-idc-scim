#!/usr/bin/env python3
"""
AWS Identity Center SCIM 用户和组同步 (JSON → IDC)
使用 scim2-client 库
"""
import argparse
import json
import sys
from pathlib import Path
from httpx import Client
from scim2_models import User, EnterpriseUser, Email, Name, Manager, Group, PatchOp, PatchOperation, SearchRequest
from scim2_client.engines.httpx import SyncSCIMClient


def load_json(file: str) -> dict | list:
    path = Path(file)
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_user(data: dict) -> list[str]:
    """验证用户数据"""
    errors = []
    for field in ["userName", "displayName"]:
        if not data.get(field):
            errors.append(f"缺少必填字段: {field}")
    if not data.get("name", {}).get("givenName"):
        errors.append("缺少必填字段: name.givenName")
    if not data.get("name", {}).get("familyName"):
        errors.append("缺少必填字段: name.familyName")
    emails = data.get("emails", [])
    if not emails:
        errors.append("缺少必填字段: emails")
    elif len(emails) > 1:
        errors.append("emails 只能有一个值")
    return errors


def validate_group(data: dict) -> list[str]:
    """验证组数据"""
    errors = []
    if not data.get("displayName"):
        errors.append("缺少必填字段: displayName")
    return errors


def build_user(UserModel, data: dict):
    """构建 SCIM User"""
    user = UserModel(
        user_name=data["userName"],
        name=Name(family_name=data["name"]["familyName"], given_name=data["name"]["givenName"]),
        display_name=data["displayName"],
        emails=[Email(value=e["value"], type=e.get("type", "work"), primary=e.get("primary", True)) 
                for e in data["emails"]],
        active=data.get("active", True),
        title=data.get("title"),
        user_type=data.get("userType"),
    )
    
    # 企业扩展字段
    ent_fields = ["employeeNumber", "costCenter", "organization", "division", "department", "manager"]
    if any(k in data for k in ent_fields):
        user[EnterpriseUser] = EnterpriseUser(
            employee_number=data.get("employeeNumber"),
            cost_center=data.get("costCenter"),
            organization=data.get("organization"),
            division=data.get("division"),
            department=data.get("department"),
            manager=Manager(value=data["manager"], ref=None) if "manager" in data else None,
        )
    return user


def user_to_dict(user) -> dict:
    """SCIM User → 可比较字典"""
    d = user.model_dump(exclude_none=True, by_alias=True, mode="json")
    d.pop("schemas", None)
    d.pop("id", None)
    d.pop("meta", None)
    return d


def normalize_local_user(UserModel, data: dict) -> dict:
    """标准化本地用户数据"""
    return user_to_dict(build_user(UserModel, data))


# ========== 用户同步 ==========

def sync_users(scim: SyncSCIMClient, UserModel, local_users: list, allow_delete: bool, dry_run: bool) -> dict:
    """同步用户"""
    stats = {"created": [], "updated": [], "deleted": [], "unchanged": [], "errors": []}
    
    print("获取 IDC 用户...")
    response = scim.query(UserModel)
    idc_users = {u.user_name: u for u in (response.resources or [])}
    print(f"IDC: {len(idc_users)} 个, 本地: {len(local_users)} 个\n")
    
    local_names = {u["userName"] for u in local_users}
    
    for data in local_users:
        name = data["userName"]
        errors = validate_user(data)
        if errors:
            print(f"  ✗ {name}: 验证失败 - {', '.join(errors)}")
            stats["errors"].append(name)
            continue
        
        try:
            if name in idc_users:
                if normalize_local_user(UserModel, data) == user_to_dict(idc_users[name]):
                    print(f"  ○ {name}")
                    stats["unchanged"].append(name)
                else:
                    print(f"  ↻ {name}" + (" (预览)" if dry_run else ""))
                    if not dry_run:
                        user = build_user(UserModel, data)
                        user.id = idc_users[name].id
                        scim.replace(user)
                    stats["updated"].append(name)
            else:
                print(f"  + {name}" + (" (预览)" if dry_run else ""))
                if not dry_run:
                    scim.create(build_user(UserModel, data))
                stats["created"].append(name)
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            stats["errors"].append(name)
    
    if allow_delete:
        for name, user in idc_users.items():
            if name not in local_names:
                try:
                    print(f"  - {name}" + (" (预览)" if dry_run else ""))
                    if not dry_run:
                        scim.delete(UserModel, user.id)
                    stats["deleted"].append(name)
                except Exception as e:
                    print(f"  ✗ {name}: {e}")
                    stats["errors"].append(name)
    
    return stats


# ========== 组同步 ==========

def get_group_actual_members(scim: SyncSCIMClient, GroupModel, group_id: str, all_user_ids: list[str]) -> set[str]:
    """获取组的实际成员 (遍历所有用户检查组成员关系)"""
    members = set()
    for user_id in all_user_ids:
        response = scim.query(GroupModel, search_request=SearchRequest(filter=f'members.value eq "{user_id}"'))
        for g in (response.resources or []):
            if g.id == group_id:
                members.add(user_id)
                break
    return members


def sync_groups(scim: SyncSCIMClient, GroupModel, UserModel, local_groups: list, allow_delete: bool, dry_run: bool) -> dict:
    """同步组"""
    stats = {"created": [], "updated": [], "deleted": [], "unchanged": [], "errors": []}
    
    if not local_groups:
        print("无组数据，跳过组同步\n")
        return stats
    
    print("获取 IDC 组...")
    response = scim.query(GroupModel)
    idc_groups = {g.display_name: g for g in (response.resources or [])}
    response = scim.query(UserModel)
    idc_users = {u.user_name: u for u in (response.resources or [])}
    print(f"IDC: {len(idc_groups)} 个组, 本地: {len(local_groups)} 个组\n")
    
    user_id_map = {u.user_name: u.id for u in idc_users.values()}
    all_user_ids = list(user_id_map.values())
    local_names = {g["displayName"] for g in local_groups}
    
    for data in local_groups:
        name = data["displayName"]
        errors = validate_group(data)
        if errors:
            print(f"  ✗ {name}: 验证失败 - {', '.join(errors)}")
            stats["errors"].append(name)
            continue
        
        # 解析本地成员
        local_member_ids = set()
        for m in data.get("members", []):
            member_name = m.get("value") if isinstance(m, dict) else m
            if member_name in user_id_map:
                local_member_ids.add(user_id_map[member_name])
            else:
                print(f"  ⚠ {name}: 成员 {member_name} 不存在于 IDC")
        
        try:
            if name in idc_groups:
                group = idc_groups[name]
                current_members = get_group_actual_members(scim, GroupModel, group.id, all_user_ids)
                
                if local_member_ids == current_members:
                    print(f"  ○ {name}")
                    stats["unchanged"].append(name)
                else:
                    to_add = local_member_ids - current_members
                    to_remove = current_members - local_member_ids
                    changes = []
                    if to_add:
                        changes.append(f"+{len(to_add)}")
                    if to_remove:
                        changes.append(f"-{len(to_remove)}")
                    
                    print(f"  ↻ {name} ({','.join(changes)})" + (" (预览)" if dry_run else ""))
                    if not dry_run:
                        operations = []
                        if to_add:
                            operations.append(PatchOperation(op=PatchOperation.Op.add, path="members", 
                                                            value=[{"value": uid} for uid in to_add]))
                        for uid in to_remove:
                            operations.append(PatchOperation(op=PatchOperation.Op.remove, 
                                                            path=f'members[value eq "{uid}"]'))
                        if operations:
                            scim.modify(GroupModel, group.id, PatchOp[GroupModel](operations=operations))
                    stats["updated"].append(name)
            else:
                print(f"  + {name}" + (" (预览)" if dry_run else ""))
                if not dry_run:
                    new_group = scim.create(GroupModel(display_name=name))
                    if local_member_ids:
                        operations = [PatchOperation(op=PatchOperation.Op.add, path="members",
                                                    value=[{"value": uid} for uid in local_member_ids])]
                        scim.modify(GroupModel, new_group.id, PatchOp[GroupModel](operations=operations))
                stats["created"].append(name)
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            stats["errors"].append(name)
    
    if allow_delete:
        for name, group in idc_groups.items():
            if name not in local_names:
                try:
                    print(f"  - {name}" + (" (预览)" if dry_run else ""))
                    if not dry_run:
                        scim.delete(GroupModel, group.id)
                    stats["deleted"].append(name)
                except Exception as e:
                    print(f"  ✗ {name}: {e}")
                    stats["errors"].append(name)
    
    return stats


# ========== 主函数 ==========

def main():
    parser = argparse.ArgumentParser(description='AWS IDC SCIM 用户和组同步')
    parser.add_argument('--delete', action='store_true', help='删除 IDC 中多余的用户和组')
    parser.add_argument('--dry-run', action='store_true', help='预览模式')
    parser.add_argument('--users-only', action='store_true', help='仅同步用户')
    parser.add_argument('--groups-only', action='store_true', help='仅同步组')
    args = parser.parse_args()
    
    print("=== AWS IDC SCIM 同步 ===\n")
    if args.dry_run:
        print("【预览模式】\n")
    if args.delete:
        print("【已启用删除】\n")
    
    config = load_json("scim-config.json")
    if not config or not isinstance(config, dict):
        print("错误: scim-config.json 不存在或格式错误")
        return 1
    
    client = Client(
        base_url=config["scim_endpoint"],
        headers={"Authorization": f"Bearer {config['scim_token']}", "Content-Type": "application/scim+json"},
        timeout=30.0
    )
    
    UserModel = User[EnterpriseUser]
    GroupModel = Group
    scim = SyncSCIMClient(client, resource_models=[UserModel, GroupModel])
    scim.register_naive_resource_types()
    
    total_errors = 0
    
    if not args.groups_only:
        print("--- 用户同步 ---\n")
        user_stats = sync_users(scim, UserModel, load_json("users.json"), args.delete, args.dry_run)
        print(f"\n用户: 创建:{len(user_stats['created'])} 更新:{len(user_stats['updated'])} 删除:{len(user_stats['deleted'])} 无变化:{len(user_stats['unchanged'])} 错误:{len(user_stats['errors'])}\n")
        total_errors += len(user_stats['errors'])
    
    if not args.users_only:
        print("--- 组同步 ---\n")
        group_stats = sync_groups(scim, GroupModel, UserModel, load_json("groups.json"), args.delete, args.dry_run)
        print(f"\n组: 创建:{len(group_stats['created'])} 更新:{len(group_stats['updated'])} 删除:{len(group_stats['deleted'])} 无变化:{len(group_stats['unchanged'])} 错误:{len(group_stats['errors'])}\n")
        total_errors += len(group_stats['errors'])
    
    client.close()
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
