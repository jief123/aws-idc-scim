#!/bin/bash

SERVICE_ID="xxxxxx"
SERVICE_SECRET="xxxxxxxx"
GROUP_NAME="AWS-Cloud-SSO"
TOKEN_URL="https://adkeeper.dun.mi.com/api/v1/getAccessToken"
ADD_URL="https://adkeeper.dun.mi.com/api/v1/adgroup/members/add"
BATCH_SIZE=100

get_token() {
    curl -s -X POST "$TOKEN_URL" \
        -H "Content-Type: application/json" \
        -d "{\"serviceId\":\"$SERVICE_ID\",\"serviceSecret\":\"$SERVICE_SECRET\"}" \
        | jq -r '.data'
}

csv_file="$1"
[ -z "$csv_file" ] && { echo "用法: $0 <csv文件>"; exit 1; }

# 提取邮箱前缀
prefixes=$(awk -F',' '
NR==1 {
    for(i=1;i<=NF;i++) {
        gsub(/"/, "", $i)
        if($i ~ /^(email|邮箱|Email)$/) {
            col=i
            break
        }
    }
    next
}
col {
    gsub(/"/, "", $col)
    split($col, a, "@")
    print a[1]
}' "$csv_file")

# 分批处理
echo "$prefixes" | xargs -n $BATCH_SIZE | while read -r batch; do
    members=$(echo "$batch" | tr ' ' ',')
    token=$(get_token)
    
    echo "处理批次: $(echo "$batch" | wc -w) 个成员"
    echo "成员列表: $members"
    echo "执行命令:"
    echo "curl -X POST '$ADD_URL' \\"
    echo "  -H 'Authorization: $token' \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"groupName\":\"$GROUP_NAME\",\"members\":\"$members\"}'"
    echo
    
    curl -X POST "$ADD_URL" \
        -H "Authorization: $token" \
        -H "Content-Type: application/json" \
        -d "{\"groupName\":\"$GROUP_NAME\",\"members\":\"$members\"}"
    echo
done
