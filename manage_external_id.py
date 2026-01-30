#!/usr/bin/env python3
"""管理 IDC 用户的 externalId"""

import json
import uuid
from aws_idc_scim import SCIMClient, PatchOperation


def load_config():
    with open("scim-config.json") as f:
        return json.load(f)


def list_users_external_id(client: SCIMClient):
    """列出所有用户的 externalId"""
    users = client.get_all_users()
    
    print(f"\n{'用户名':<30} {'externalId':<40} {'状态'}")
    print("-" * 80)
    
    missing_count = 0
    for user in users:
        username = user.userName
        external_id = user.externalId or ""
        status = "✓" if external_id else "✗ 缺失"
        
        if not external_id:
            missing_count += 1
        
        print(f"{username:<30} {external_id:<40} {status}")
    
    print(f"\n总计: {len(users)} 个用户, {missing_count} 个缺失 externalId")
    return users


def set_external_id(client: SCIMClient, username: str, external_id: str | None = None):
    """为用户设置 externalId"""
    user = client.find_user_by_username(username)
    if not user or not user.id:
        print(f"✗ 用户不存在: {username}")
        return False
    
    if not external_id:
        external_id = str(uuid.uuid4())
    
    try:
        client.patch_user(user.id, [PatchOperation(op="replace", path="externalId", value=external_id)])
        print(f"✓ 已设置 {username} 的 externalId: {external_id}")
        return True
    except Exception as e:
        print(f"✗ 设置失败: {e}")
        return False


def auto_set_missing_external_ids(client: SCIMClient, dry_run: bool = False):
    """自动为缺失 externalId 的用户设置 UUID"""
    users = client.get_all_users()
    missing_users = [u for u in users if not u.externalId]
    
    if not missing_users:
        print("\n✓ 所有用户都已有 externalId")
        return
    
    print(f"\n发现 {len(missing_users)} 个用户缺失 externalId:")
    
    for user in missing_users:
        username = user.userName
        external_id = str(uuid.uuid4())
        
        if dry_run:
            print(f"[预览] {username} -> {external_id}")
        else:
            try:
                if user.id:
                    client.patch_user(user.id, [PatchOperation(op="replace", path="externalId", value=external_id)])
                    print(f"✓ {username} -> {external_id}")
            except Exception as e:
                print(f"✗ {username} 设置失败: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="管理 IDC 用户的 externalId")
    parser.add_argument("command", choices=["list", "set", "auto-set"], 
                       help="list: 列出所有用户的 externalId | set: 设置指定用户 | auto-set: 自动设置缺失的")
    parser.add_argument("--username", help="用户名 (用于 set 命令)")
    parser.add_argument("--external-id", help="externalId 值 (可选，默认生成 UUID)")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际修改")
    
    args = parser.parse_args()
    
    config = load_config()
    client = SCIMClient(config["scim_endpoint"], config["scim_token"])
    
    try:
        if args.command == "list":
            list_users_external_id(client)
        
        elif args.command == "set":
            if not args.username:
                print("错误: --username 参数必需")
                return
            set_external_id(client, args.username, args.external_id)
        
        elif args.command == "auto-set":
            auto_set_missing_external_ids(client, args.dry_run)
    
    finally:
        client.close()


if __name__ == "__main__":
    main()
