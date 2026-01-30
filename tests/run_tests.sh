#!/bin/bash
# CLI 测试脚本

# 不用 set -e，我们自己处理错误
cd "$(dirname "$0")/.."

CLI="python3 scim_cli.py"
DATA="tests/data"
PASSED=0
FAILED=0

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "${GREEN}✓ $1${NC}"; ((PASSED++)); }
log_fail() { echo -e "${RED}✗ $1${NC}"; ((FAILED++)); }
log_info() { echo -e "${YELLOW}► $1${NC}"; }

# 检查命令是否成功
expect_success() {
    output=$(eval "$1" 2>&1)
    ret=$?
    if [ $ret -eq 0 ]; then
        log_pass "$2"
    else
        log_fail "$2 (退出码: $ret)"
        echo "    输出: $output"
    fi
}

# 检查命令是否失败
expect_fail() {
    output=$(eval "$1" 2>&1)
    ret=$?
    if [ $ret -ne 0 ]; then
        log_pass "$2"
    else
        log_fail "$2 (应该失败但成功了，退出码: $ret)"
        echo "    输出: $output"
    fi
}

# 检查输出包含某字符串
expect_contains() {
    output=$(eval "$1" 2>&1)
    ret=$?
    if echo "$output" | grep -q "$2"; then
        log_pass "$3"
    else
        log_fail "$3 (输出不包含: $2)"
        echo "    退出码: $ret"
        echo "    输出: $output"
    fi
}

# ========== 用户 CRUD 测试 ==========
test_user_crud() {
    log_info "用户 CRUD 测试"
    
    # 列出用户
    expect_success "$CLI user list" "列出所有用户"
    expect_success "$CLI user list --format json" "列出用户 (JSON)"
    
    # 获取用户
    expect_contains "$CLI user get zhangsan@example.com" "zhangsan" "获取存在的用户"
    expect_fail "$CLI user get notexist_user_12345@example.com" "获取不存在的用户"
    
    # 创建用户
    expect_success "$CLI user create $DATA/new_user.json" "创建新用户"
    expect_fail "$CLI user create $DATA/new_user.json" "创建已存在用户"
    
    # 更新用户 (用户已存在)
    expect_success "$CLI user update $DATA/update_user.json" "更新用户"
    
    # 删除用户
    expect_success "$CLI user delete testuser@example.com" "删除用户"
    expect_fail "$CLI user delete testuser@example.com" "删除不存在用户"
}

# ========== 用户同步测试 ==========
test_user_sync() {
    log_info "用户同步测试"
    
    # 先创建测试用户
    $CLI user create $DATA/sync_users.json > /dev/null 2>&1 || true
    
    # 增量同步 - dry-run
    expect_contains "$CLI user sync $DATA/sync_users.json --dry-run" "无变化\|创建\|更新" "用户增量同步 (dry-run)"
    
    # 增量同步
    expect_success "$CLI user sync $DATA/sync_users.json" "用户增量同步"
    
    # 全量同步 (不删除)
    expect_success "$CLI user full-sync $DATA/sync_users.json" "用户全量同步 (不删除)"
    
    # 全量同步 --delete (dry-run)
    expect_contains "$CLI user full-sync $DATA/sync_users.json --delete --dry-run" "同步" "用户全量同步 --delete (dry-run)"
}

# ========== 组 CRUD 测试 ==========
test_group_crud() {
    log_info "组 CRUD 测试"
    
    # 列出组
    expect_success "$CLI group list" "列出所有组"
    
    # 创建组
    expect_success "$CLI group create CLI测试组" "创建新组"
    expect_fail "$CLI group create CLI测试组" "创建已存在组"
    
    # 删除组
    expect_success "$CLI group delete CLI测试组" "删除组"
    expect_fail "$CLI group delete CLI测试组" "删除不存在组"
}

# ========== 组成员测试 ==========
test_group_member() {
    log_info "组成员测试"
    
    # 确保测试组存在
    $CLI group create 成员测试组 > /dev/null 2>&1 || true
    
    # 列出成员
    expect_success "$CLI group list-members 开发组" "列出组成员"
    expect_fail "$CLI group list-members 不存在的组12345" "列出不存在组的成员"
    
    # 添加成员
    expect_success "$CLI group add-member 成员测试组 zhangsan@example.com" "添加成员"
    expect_fail "$CLI group add-member 成员测试组 notexist_user_12345@example.com" "添加不存在的用户"
    expect_fail "$CLI group add-member 不存在的组12345 zhangsan@example.com" "添加到不存在的组"
    
    # 移除成员
    expect_success "$CLI group remove-member 成员测试组 zhangsan@example.com" "移除成员"
    
    # 清理
    $CLI group delete 成员测试组 > /dev/null 2>&1 || true
}

# ========== 组同步测试 ==========
test_group_sync() {
    log_info "组同步测试"
    
    # 确保测试用户存在
    $CLI user create $DATA/sync_users.json > /dev/null 2>&1 || true
    
    # 增量同步 - dry-run
    expect_contains "$CLI group sync $DATA/sync_groups.json --dry-run" "同步" "组增量同步 (dry-run)"
    
    # 增量同步
    expect_success "$CLI group sync $DATA/sync_groups.json" "组增量同步"
    
    # 全量同步 (不删组)
    expect_success "$CLI group full-sync $DATA/sync_groups.json" "组全量同步 (不删组)"
    
    # 全量同步 --delete (dry-run)
    expect_contains "$CLI group full-sync $DATA/sync_groups.json --delete --dry-run" "同步" "组全量同步 --delete (dry-run)"
}

# ========== CSV 导入测试 ==========
test_csv_import() {
    log_info "CSV 导入测试"
    
    # 正常导入
    expect_contains "$CLI group import-csv $DATA/import.csv -o tests/data/import_output.json" "写入" "CSV 正常导入"
    
    # 空 CSV
    expect_contains "$CLI group import-csv $DATA/import_empty.csv -o tests/data/empty_output.json" "没有有效数据" "空 CSV 导入"
    
    # 无效列
    expect_contains "$CLI group import-csv $DATA/import_invalid.csv -o tests/data/invalid_output.json" "没有有效数据" "无效列 CSV 导入"
    
    # 清理
    rm -f tests/data/import_output.json tests/data/empty_output.json tests/data/invalid_output.json
}

# ========== 验证测试 ==========
test_validation() {
    log_info "数据验证测试"
    
    expect_fail "$CLI user create $DATA/invalid_user_no_username.json" "缺少 userName"
    expect_fail "$CLI user create $DATA/invalid_user_no_email.json" "缺少 emails"
    expect_fail "$CLI user create $DATA/invalid_user_multi_email.json" "多个 emails"
}

# ========== 清理测试数据 ==========
cleanup() {
    log_info "清理测试数据"
    $CLI user delete sync_user1@example.com > /dev/null 2>&1 || true
    $CLI user delete sync_user2@example.com > /dev/null 2>&1 || true
    $CLI group delete 测试组A > /dev/null 2>&1 || true
    $CLI group delete 测试组B > /dev/null 2>&1 || true
    $CLI group delete 导入测试组 > /dev/null 2>&1 || true
}

# ========== 主函数 ==========
main() {
    echo "=============================="
    echo "  SCIM CLI 测试"
    echo "=============================="
    echo ""
    
    case "${1:-all}" in
        user_crud)    test_user_crud ;;
        user_sync)    test_user_sync ;;
        group_crud)   test_group_crud ;;
        group_member) test_group_member ;;
        group_sync)   test_group_sync ;;
        csv_import)   test_csv_import ;;
        validation)   test_validation ;;
        cleanup)      cleanup ;;
        all)
            test_user_crud
            echo ""
            test_user_sync
            echo ""
            test_group_crud
            echo ""
            test_group_member
            echo ""
            test_group_sync
            echo ""
            test_csv_import
            echo ""
            test_validation
            echo ""
            cleanup
            ;;
        *)
            echo "用法: $0 [user_crud|user_sync|group_crud|group_member|group_sync|csv_import|validation|cleanup|all]"
            exit 1
            ;;
    esac
    
    echo ""
    echo "=============================="
    echo -e "  通过: ${GREEN}$PASSED${NC}  失败: ${RED}$FAILED${NC}"
    echo "=============================="
    
    [ $FAILED -eq 0 ]
}

main "$@"
