#!/usr/bin/env python3
"""清空指定组的所有成员"""

import json
import sys
from aws_idc_scim import SCIMClient, SCIMGroup


def load_config():
    with open("scim-config.json") as f:
        return json.load(f)


def clear_group_members(client: SCIMClient, group_name: str, dry_run: bool = False):
    """清空组的所有成员"""
    
    print(f"{'[预览]' if dry_run else ''} 清空组 '{group_name}' 的所有成员")
    
    # 使用 full_sync 移除所有成员（空成员列表）
    groups = [SCIMGroup(displayName=group_name)]
    members_map = {group_name: []}  # 空成员列表
    
    result = client.full_sync_groups(groups, members_map, allow_delete=False, dry_run=dry_run)
    
    print(f"\n结果:")
    
    # 检查 details 中的移除成员信息
    if group_name in result.details:
        removed_members = result.details[group_name].get("removed", [])
        if removed_members:
            print(f"  移除成员: {len(removed_members)} 个")
            for member in removed_members:
                print(f"    - {member['userName']} [id: {member['id']}]")
        else:
            print(f"  该组已经没有成员")
    else:
        print(f"  未发现变化")
    
    if result.errors:
        print(f"\n  错误: {len(result.errors)} 个")
        for error in result.errors:
            print(f"    ✗ {error}")
        return False
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="清空组的所有成员")
    parser.add_argument("group_name", help="组名")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    
    args = parser.parse_args()
    
    config = load_config()
    client = SCIMClient(config["scim_endpoint"], config["scim_token"])
    
    try:
        # 检查组是否存在
        group = client.find_group_by_name(args.group_name)
        if not group:
            print(f"✗ 组不存在: {args.group_name}")
            sys.exit(1)
        
        success = clear_group_members(client, args.group_name, args.dry_run)
        sys.exit(0 if success else 1)
    
    finally:
        client.close()


if __name__ == "__main__":
    main()
