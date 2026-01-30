#!/usr/bin/env python3
"""将 kiro 名单 CSV 转换为 group import-csv 格式"""

import csv
import sys


# 套餐到组名的映射
PLAN_TO_GROUP = {
    "Kiro Pro+(2000 Credits)": "aws-global-kiro-proplus",
    "Kiro Pro(1000 Credits)": "aws-global-kiro-pro",
    "Kiro Power(10000 Credits)": "aws-global-kiro-power",
}


def convert_csv(input_file, output_file):
    """转换 CSV 格式"""
    
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        
        # 统计
        stats = {}
        rows = []
        
        for row in reader:
            plan = row.get('开通套餐', '').strip()
            username = row.get('用户名', '').strip()
            email = row.get('邮箱', '').strip()
            
            if not username:
                print(f"⚠️  跳过：缺少用户名 - {row}")
                continue
            
            # 映射到组名
            group_name = PLAN_TO_GROUP.get(plan)
            
            if not group_name:
                print(f"⚠️  未知套餐类型: {plan} (用户: {username})")
                continue
            
            # 添加 @xiaomi.com 后缀（如果需要）
            if email and '@' in email:
                member_identifier = email
            elif '@' not in username:
                member_identifier = f"{username}@xiaomi.com"
            else:
                member_identifier = username
            
            rows.append({
                'group_name': group_name,
                'member': member_identifier
            })
            
            # 统计
            stats[group_name] = stats.get(group_name, 0) + 1
    
    # 写入输出文件
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['group_name', 'member'])
        writer.writeheader()
        writer.writerows(rows)
    
    # 打印统计
    print(f"\n✓ 转换完成: {output_file}")
    print(f"\n统计:")
    for group, count in sorted(stats.items()):
        print(f"  {group}: {count} 个成员")
    print(f"\n总计: {sum(stats.values())} 个成员")
    
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="转换 kiro 名单为 group import-csv 格式")
    parser.add_argument("input_file", help="输入 CSV 文件")
    parser.add_argument("-o", "--output", default="kiro_groups.csv", help="输出文件名 (默认: kiro_groups.csv)")
    
    args = parser.parse_args()
    
    try:
        convert_csv(args.input_file, args.output)
        print(f"\n下一步:")
        print(f"  python scim_cli.py group import-csv {args.output}")
    except Exception as e:
        print(f"✗ 错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
