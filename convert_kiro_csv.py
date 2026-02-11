#!/usr/bin/env python3
"""遍历 CSV 的 charge_uuid 列，通过 SCIM 查询 username 并替换"""

import csv
import sys
import re
from aws_idc_scim.client import SCIMClient

def load_config():
    import json
    with open("scim-config.json") as f:
        return json.load(f)

def extract_user_id(arn: str) -> str | None:
    """从 arn:aws:identitystore:::user/xxx 中提取 user_id"""
    m = re.search(r'user/([a-f0-9-]+)', arn)
    return m.group(1) if m else None

def main():
    csv_file = sys.argv[1] if len(sys.argv) > 1 else "kiro_bill_parsed.csv"
    
    config = load_config()
    client = SCIMClient(config["scim_endpoint"], config["scim_token"])
    
    # 缓存 user_id -> username，避免重复查询
    cache = {}
    
    # 读取 CSV
    with open(csv_file, newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # 遍历所有列的所有单元格，按内容匹配 identitystore ARN
    for row in rows:
        for col in fieldnames:
            val = row[col]
            user_id = extract_user_id(val)
            if not user_id:
                continue
            
            if user_id not in cache:
                try:
                    user = client.get_user(user_id)
                    cache[user_id] = user.userName
                    print(f"  {user_id} -> {user.userName}")
                except Exception as e:
                    print(f"  查询失败 {user_id}: {e}")
                    cache[user_id] = val  # 查询失败保留原值
            
            row[col] = cache[user_id]
    
    client.close()
    
    # 写回 CSV
    with open(csv_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"\n完成，已更新 {csv_file}")

if __name__ == "__main__":
    main()
