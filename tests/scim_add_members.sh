#!/bin/bash

csv_file="$1"
[ -z "$csv_file" ] && { echo "用法: $0 <csv文件>"; exit 1; }

# 提取组名和邮箱前缀
awk -F',' 'BEGIN{RS="\r?\n"}
NR==1 {
    for(i=1;i<=NF;i++) {
        gsub(/"/, "", $i)
        if($i ~ /^(email|邮箱|Email)$/) email_col=i
        if($i ~ /^(group|组|Group)$/) group_col=i
    }
    next
}
email_col && group_col {
    gsub(/"/, "", $email_col)
    gsub(/"/, "", $group_col)
    split($email_col, a, "@")
    print $group_col "," a[1]
}' "$csv_file" | while IFS=',' read -r group user; do
    echo "执行: python3.13 scim_cli group add-member \"$group\" \"$user\""
    python3.13 scim_cli group add-member "$group" "$user"
done
