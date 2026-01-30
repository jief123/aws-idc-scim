#!/usr/bin/env python3
"""测试 SCIM 用户身份标识的变化规则"""

import json
import time
import uuid
from aws_idc_scim import SCIMClient, SCIMUser, SCIMName, SCIMEmail, PatchOperation


def load_config():
    with open("scim-config.json") as f:
        return json.load(f)


def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_user_info(label, user: SCIMUser | None):
    """打印用户关键信息"""
    if not user:
        print(f"{label}: 用户不存在")
        return
    
    email = user.emails[0].value if user.emails else 'N/A'
    print(f"{label}:")
    print(f"  - id (IDC内部ID): {user.id or 'N/A'}")
    print(f"  - userName:       {user.userName}")
    print(f"  - email:          {email}")
    print(f"  - externalId:     {user.externalId or 'N/A'}")
    print()


def create_test_user(client: SCIMClient, username: str, email: str, display_name: str, external_id: str | None = None) -> SCIMUser:
    """创建测试用户"""
    user = SCIMUser(
        userName=username,
        displayName=display_name,
        name=SCIMName(familyName="测试", givenName=display_name),
        emails=[SCIMEmail(value=email, type="work", primary=True)],
        externalId=external_id,
        active=True,
    )
    return client.create_user(user)


def test_scenario_1(client: SCIMClient):
    """场景1: userName 相同，修改 email，观察 user id 是否变化"""
    print_section("场景1: userName 相同，修改 email")
    
    username = "test.scenario1@example.com"
    
    # 清理可能存在的用户
    existing = client.find_user_by_username(username)
    if existing and existing.id:
        client.delete_user(existing.id)
    
    # 步骤1: 创建用户
    print("步骤1: 创建用户")
    created = create_test_user(client, username, "original.email@example.com", "测试场景1")
    print_user_info("创建后", created)
    original_id = created.id
    time.sleep(1)
    
    # 步骤2: 修改 email
    print("步骤2: 修改 email (userName 保持不变)")
    try:
        client.patch_user(original_id, [
            PatchOperation(op="replace", path="emails", value=[{"value": "changed.email@example.com", "type": "work", "primary": True}])
        ])
        updated = client.find_user_by_username(username)
        print_user_info("修改后", updated)
        new_id = updated.id if updated else None
        
        print(f"结果: user id {'未变化 ✓' if original_id == new_id else '已变化 ✗'}")
        print(f"  原始 id: {original_id}")
        print(f"  新的 id: {new_id}")
    except Exception as e:
        print(f"✗ 更新失败: {e}")
    
    # 清理
    print("\n清理测试数据...")
    if original_id:
        client.delete_user(original_id)


def test_scenario_2(client: SCIMClient):
    """场景2: email 相同，修改 userName，观察 user id 是否变化"""
    print_section("场景2: email 相同，修改 userName")
    
    test_email = "fixed.email@example.com"
    username = "test.scenario2a@example.com"
    
    # 清理可能存在的用户
    for name in [username, "test.scenario2b@example.com"]:
        existing = client.find_user_by_username(name)
        if existing and existing.id:
            client.delete_user(existing.id)
    
    # 步骤1: 创建用户
    print("步骤1: 创建用户 (userName: test.scenario2a)")
    created = create_test_user(client, username, test_email, "测试场景2A")
    print_user_info("创建后", created)
    original_id = created.id
    time.sleep(1)
    
    # 步骤2: 尝试修改 userName
    print("步骤2: 尝试修改 userName (email 保持不变)")
    print("注意: IDC 可能不允许直接修改 userName，这是测试的关键点")
    
    try:
        client.patch_user(original_id, [
            PatchOperation(op="replace", path="userName", value="test.scenario2b@example.com")
        ])
        updated = client.get_user(original_id)
        print_user_info("修改后", updated)
        
        print(f"结果: user id 未变化 ✓ (userName 修改成功)")
        print(f"  id: {original_id}")
    except Exception as e:
        print(f"✗ 更新失败 (这可能是预期行为): {e}")
        print("说明: IDC 可能将 userName 作为不可变标识符")
    
    # 清理
    print("\n清理测试数据...")
    if original_id:
        client.delete_user(original_id)


def test_scenario_3(client: SCIMClient):
    """场景3: 有 externalId，修改 userName，观察 user id 是否变化"""
    print_section("场景3: 有 externalId，externalId 相同时修改 userName")
    
    external_id = str(uuid.uuid4())
    username = "test.scenario3a@example.com"
    
    # 清理可能存在的用户
    for name in [username, "test.scenario3b@example.com"]:
        existing = client.find_user_by_username(name)
        if existing and existing.id:
            client.delete_user(existing.id)
    
    # 步骤1: 创建带 externalId 的用户
    print(f"步骤1: 创建用户 (externalId: {external_id})")
    created = create_test_user(client, username, "scenario3a@example.com", "测试场景3A", external_id)
    print_user_info("创建后", created)
    original_id = created.id
    time.sleep(1)
    
    # 步骤2: 修改 userName
    print("步骤2: 修改 userName (externalId 保持不变)")
    try:
        client.patch_user(original_id, [
            PatchOperation(op="replace", path="userName", value="test.scenario3b@example.com"),
            PatchOperation(op="replace", path="emails", value=[{"value": "scenario3b@example.com", "type": "work", "primary": True}])
        ])
        updated = client.get_user(original_id)
        print_user_info("修改后", updated)
        
        print(f"结果: user id 未变化 ✓")
        print(f"  id: {original_id}")
        print(f"\n关键发现: externalId 是否作为稳定标识符？")
    except Exception as e:
        print(f"✗ 更新失败: {e}")
        print("说明: 即使有 externalId，userName 可能仍然不可变")
    
    # 清理
    print("\n清理测试数据...")
    if original_id:
        client.delete_user(original_id)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="测试 SCIM 用户身份标识规则")
    parser.add_argument("--scenario", type=int, choices=[1, 2, 3], 
                       help="运行指定场景 (1, 2, 或 3)，不指定则运行全部")
    
    args = parser.parse_args()
    
    config = load_config()
    client = SCIMClient(config["scim_endpoint"], config["scim_token"])
    
    try:
        print("\n" + "="*80)
        print("  AWS Identity Center SCIM 用户身份标识测试")
        print("="*80)
        print("\n测试目标:")
        print("  1. userName 相同，修改 email → user id 是否变化？")
        print("  2. email 相同，修改 userName → user id 是否变化？")
        print("  3. 有 externalId，修改 userName → user id 是否变化？")
        print("\n注意: 测试会创建和删除临时用户")
        
        input("\n按 Enter 继续...")
        
        if args.scenario is None or args.scenario == 1:
            test_scenario_1(client)
        
        if args.scenario is None or args.scenario == 2:
            test_scenario_2(client)
        
        if args.scenario is None or args.scenario == 3:
            test_scenario_3(client)
        
        print_section("测试总结")
        print("根据 AWS 文档和 SCIM 标准:")
        print("  - userName 是主要标识符，通常不可变")
        print("  - email 可以修改，不影响 user id")
        print("  - externalId 是推荐的稳定外部标识符")
        print("  - IDC 内部的 'id' 字段是系统生成的不可变唯一标识")
        print("\n实际行为请参考上述测试结果。")
        
    finally:
        client.close()


if __name__ == "__main__":
    main()
