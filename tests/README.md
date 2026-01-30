# CLI 测试计划

## 测试前准备

```bash
cd tests
# 确保 IDC 中有基础数据用于测试
```

## 运行测试

```bash
# 运行所有测试
./run_tests.sh

# 或单独运行某个测试
./run_tests.sh user_crud
./run_tests.sh user_sync
./run_tests.sh group_crud
./run_tests.sh group_member
./run_tests.sh group_sync
./run_tests.sh csv_import
./run_tests.sh validation
```

## 测试数据文件

- `data/new_user.json` - 新用户
- `data/update_user.json` - 更新用户
- `data/invalid_user_*.json` - 无效用户数据
- `data/sync_users.json` - 用户同步测试
- `data/sync_groups.json` - 组同步测试
- `data/import.csv` - CSV 导入测试
