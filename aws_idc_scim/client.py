"""
AWS IDC SCIM HTTP Client

使用 httpx 实现，处理 AWS IDC 特有的行为：
- nextCursor 分页
- 错误响应中的额外字段
- PUT User 需要包含 id
- Group 成员操作只能用 PATCH
"""

from typing import Iterator
from httpx import Client, Response

from .models import (
    SCIMUser,
    SCIMGroup,
    PatchOp,
    PatchOperation,
    PatchOpType,
    ListResponse,
    SCIMError,
    SyncResult,
)


class SCIMClientError(Exception):
    """SCIM 客户端错误"""
    def __init__(self, message: str, error: SCIMError | None = None):
        super().__init__(message)
        self.error = error


class SCIMClient:
    """
    AWS IDC SCIM 客户端
    
    处理 AWS IDC 的 SCIM 实现限制：
    - 分页使用 nextCursor (最大 100)
    - PUT Group 不支持，使用 PATCH
    - PUT User 需要 body 包含 id
    - Filter 只支持 eq 和 and
    """
    
    MAX_PAGE_SIZE = 100
    
    def __init__(self, endpoint: str, token: str, timeout: float = 30.0):
        """
        初始化客户端
        
        Args:
            endpoint: SCIM endpoint URL
            token: Bearer token
            timeout: 请求超时时间
        """
        self.client = Client(
            base_url=endpoint.rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/scim+json",
            },
            timeout=timeout,
        )
    
    def close(self):
        """关闭连接"""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    # ============ 底层请求方法 ============
    
    def _handle_response(self, resp: Response, expected_codes: list[int] = None) -> dict | None:
        """
        处理响应，统一错误处理
        
        Args:
            resp: HTTP 响应
            expected_codes: 期望的状态码列表，默认 [200, 201, 204]
        
        Returns:
            响应 JSON 或 None (204)
        
        Raises:
            SCIMClientError: 请求失败
        """
        if expected_codes is None:
            expected_codes = [200, 201, 204]
        
        if resp.status_code in expected_codes:
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        
        # 解析错误
        try:
            error_data = resp.json()
            error = SCIMError.from_dict(error_data, resp.status_code)
        except Exception:
            error = SCIMError(status=resp.status_code, detail=resp.text)
        
        raise SCIMClientError(str(error), error)
    
    def _get(self, path: str, params: dict = None) -> dict:
        """GET 请求"""
        resp = self.client.get(path, params=params)
        return self._handle_response(resp)
    
    def _post(self, path: str, json: dict) -> dict:
        """POST 请求"""
        resp = self.client.post(path, json=json)
        return self._handle_response(resp)
    
    def _put(self, path: str, json: dict) -> dict:
        """PUT 请求"""
        resp = self.client.put(path, json=json)
        return self._handle_response(resp)
    
    def _patch(self, path: str, json: dict) -> dict | None:
        """PATCH 请求"""
        resp = self.client.patch(path, json=json)
        return self._handle_response(resp)
    
    def _delete(self, path: str) -> None:
        """DELETE 请求"""
        resp = self.client.delete(path)
        self._handle_response(resp, expected_codes=[200, 204])
    
    # ============ 分页迭代器 ============
    
    def _paginate(self, path: str, params: dict = None) -> Iterator[dict]:
        """
        分页迭代器，处理 AWS IDC 的 nextCursor 分页
        
        AWS IDC 特殊行为: 
        - /Users 第一次请求需要带空 cursor 参数才会返回 nextCursor
        - /Groups 带 filter 时不能用空 cursor
        
        Yields:
            每个资源的 dict
        """
        if params is None:
            params = {}
        params["count"] = self.MAX_PAGE_SIZE
        
        is_first_request = True
        cursor = None
        
        while True:
            # 第一次请求：如果没有 filter，用空 cursor；有 filter 则不带 cursor
            if is_first_request:
                if "filter" not in params:
                    params["cursor"] = ""
                is_first_request = False
            else:
                params["cursor"] = cursor
            
            data = self._get(path, params)
            response = ListResponse.from_dict(data)
            
            for resource in response.resources:
                yield resource
            
            if not response.next_cursor:
                break
            cursor = response.next_cursor
    
    # ============ User 操作 ============
    
    def list_users(self, filter: str = None) -> Iterator[SCIMUser]:
        """
        列出用户 (自动分页)
        
        Args:
            filter: SCIM filter (只支持 eq 和 and)
        
        Yields:
            SCIMUser 对象
        """
        params = {}
        if filter:
            params["filter"] = filter
        
        for data in self._paginate("/Users", params):
            yield SCIMUser.from_dict(data)
    
    def get_all_users(self, filter: str = None) -> list[SCIMUser]:
        """列出所有用户 (返回列表)"""
        return list(self.list_users(filter))
    
    def get_user(self, user_id: str) -> SCIMUser:
        """获取单个用户"""
        data = self._get(f"/Users/{user_id}")
        return SCIMUser.from_dict(data)
    
    def find_user_by_username(self, username: str) -> SCIMUser | None:
        """按 userName 查找用户"""
        filter = f'userName eq "{username}"'
        users = list(self.list_users(filter))
        return users[0] if users else None
    
    def create_user(self, user: SCIMUser) -> SCIMUser:
        """创建用户"""
        data = self._post("/Users", user.to_dict(for_create=True))
        return SCIMUser.from_dict(data)
    
    def update_user(self, user: SCIMUser) -> SCIMUser:
        """
        更新用户 (使用 PUT)
        
        注意: AWS IDC 要求 PUT body 包含 id
        """
        if not user.id:
            raise SCIMClientError("User id is required for update")
        
        data = self._put(f"/Users/{user.id}", user.to_dict(include_id=True))
        return SCIMUser.from_dict(data)
    
    def patch_user(self, user_id: str, operations: list[PatchOperation]) -> SCIMUser | None:
        """
        部分更新用户 (使用 PATCH)
        
        Args:
            user_id: 用户 ID
            operations: PATCH 操作列表
        
        Returns:
            更新后的用户，或 None (204)
        """
        patch = PatchOp(operations=operations)
        data = self._patch(f"/Users/{user_id}", patch.to_dict())
        return SCIMUser.from_dict(data) if data else None
    
    def delete_user(self, user_id: str) -> None:
        """删除用户"""
        self._delete(f"/Users/{user_id}")
    
    # ============ Group 操作 ============
    
    def list_groups(self, filter: str = None) -> Iterator[SCIMGroup]:
        """
        列出组 (自动分页)
        
        注意: AWS IDC 的 GET /Groups 不返回 members
        
        Args:
            filter: SCIM filter (只支持 eq 和 and)
        
        Yields:
            SCIMGroup 对象
        """
        params = {}
        if filter:
            params["filter"] = filter
        
        for data in self._paginate("/Groups", params):
            yield SCIMGroup.from_dict(data)
    
    def get_all_groups(self, filter: str = None) -> list[SCIMGroup]:
        """列出所有组 (返回列表)"""
        return list(self.list_groups(filter))
    
    def get_group(self, group_id: str) -> SCIMGroup:
        """获取单个组 (不含 members)"""
        data = self._get(f"/Groups/{group_id}")
        return SCIMGroup.from_dict(data)
    
    def find_group_by_name(self, display_name: str) -> SCIMGroup | None:
        """按 displayName 查找组"""
        filter = f'displayName eq "{display_name}"'
        groups = list(self.list_groups(filter))
        return groups[0] if groups else None
    
    def create_group(self, group: SCIMGroup) -> SCIMGroup:
        """创建组"""
        data = self._post("/Groups", group.to_dict(for_create=True))
        return SCIMGroup.from_dict(data)
    
    def delete_group(self, group_id: str) -> None:
        """删除组"""
        self._delete(f"/Groups/{group_id}")
    
    # ============ Group 成员操作 (只能用 PATCH) ============
    
    def add_group_members(self, group_id: str, user_ids: list[str]) -> None:
        """
        添加组成员
        
        AWS IDC 限制: 单次最多 100 个成员
        
        Args:
            group_id: 组 ID
            user_ids: 要添加的用户 ID 列表
        """
        if not user_ids:
            return
        
        # 分批处理
        for i in range(0, len(user_ids), self.MAX_PAGE_SIZE):
            batch = user_ids[i:i + self.MAX_PAGE_SIZE]
            op = PatchOperation(
                op=PatchOpType.ADD,
                path="members",
                value=[{"value": uid} for uid in batch],
            )
            patch = PatchOp(operations=[op])
            self._patch(f"/Groups/{group_id}", patch.to_dict())
    
    def remove_group_members(self, group_id: str, user_ids: list[str]) -> None:
        """
        移除组成员
        
        AWS IDC 限制: 单次最多 100 个操作
        
        Args:
            group_id: 组 ID
            user_ids: 要移除的用户 ID 列表
        """
        if not user_ids:
            return
        
        # 分批处理
        for i in range(0, len(user_ids), self.MAX_PAGE_SIZE):
            batch = user_ids[i:i + self.MAX_PAGE_SIZE]
            operations = [
                PatchOperation(
                    op=PatchOpType.REMOVE,
                    path=f'members[value eq "{uid}"]',
                )
                for uid in batch
            ]
            patch = PatchOp(operations=operations)
            self._patch(f"/Groups/{group_id}", patch.to_dict())
    
    def is_user_in_group(self, group_id: str, user_id: str) -> bool:
        """
        检查用户是否在组中
        
        AWS IDC 限制: 不支持 id 和 members.value 组合的 filter，
        需要先查询用户所属的所有组，再检查是否包含目标组
        """
        user_groups = self.get_user_groups(user_id)
        return any(g.id == group_id for g in user_groups)
    
    def get_user_groups(self, user_id: str) -> list[SCIMGroup]:
        """
        获取用户所属的所有组
        
        AWS IDC 限制: 需要用 filter 查询
        """
        filter = f'members.value eq "{user_id}"'
        return list(self.list_groups(filter))

    # ============ 同步操作 ============
    
    def sync_users(self, users: list[SCIMUser], dry_run: bool = False) -> SyncResult:
        """
        增量同步用户 (只添加/更新，不删除)
        
        Args:
            users: 要同步的用户列表
            dry_run: 是否只预览不执行
        
        Returns:
            SyncResult 同步结果
        """
        return self._sync_users_impl(users, allow_delete=False, dry_run=dry_run)
    
    def full_sync_users(self, users: list[SCIMUser], allow_delete: bool = False, dry_run: bool = False) -> SyncResult:
        """
        全量同步用户 (添加/更新，可选删除)
        
        Args:
            users: 要同步的用户列表
            allow_delete: 是否删除 IDC 中多余的用户
            dry_run: 是否只预览不执行
        
        Returns:
            SyncResult 同步结果
        """
        return self._sync_users_impl(users, allow_delete=allow_delete, dry_run=dry_run)
    
    def _sync_users_impl(self, users: list[SCIMUser], allow_delete: bool, dry_run: bool) -> SyncResult:
        """同步用户实现"""
        result = SyncResult()
        
        # 获取 IDC 现有用户
        idc_users = {u.userName: u for u in self.list_users()}
        local_names = {u.userName for u in users}
        
        for user in users:
            name = user.userName
            try:
                if name in idc_users:
                    idc_user = idc_users[name]
                    # 比较差异
                    local_dict = user.to_dict()
                    idc_dict = idc_user.to_dict()
                    changed_fields = self._diff_dict(local_dict, idc_dict)
                    
                    if not changed_fields:
                        result.unchanged.append(name)
                    else:
                        if not dry_run:
                            user.id = idc_user.id
                            self.update_user(user)
                        result.updated.append(name)
                        result.details[name] = {"fields": changed_fields, "id": idc_user.id}
                else:
                    if not dry_run:
                        created = self.create_user(user)
                        result.details[name] = {"id": created.id}
                    result.created.append(name)
            except Exception as e:
                result.errors.append(f"{name}: {e}")
        
        # 删除多余用户
        if allow_delete:
            for name, user in idc_users.items():
                if name not in local_names and user.id:
                    try:
                        if not dry_run:
                            self.delete_user(user.id)
                        result.deleted.append(name)
                        result.details[name] = {"id": user.id}
                    except Exception as e:
                        result.errors.append(f"{name}: {e}")
        
        return result
    
    def sync_groups(self, groups: list[SCIMGroup], members_map: dict[str, list[str]] = None, dry_run: bool = False) -> SyncResult:
        """
        增量同步组 (只创建组/添加成员，不删除组/移除成员)
        
        Args:
            groups: 要同步的组列表
            members_map: 组成员映射 {groupName: [userName, ...]}
            dry_run: 是否只预览不执行
        
        Returns:
            SyncResult 同步结果
        """
        return self._sync_groups_impl(groups, members_map, allow_delete=False, allow_remove_members=False, dry_run=dry_run)
    
    def full_sync_groups(self, groups: list[SCIMGroup], members_map: dict[str, list[str]] = None, allow_delete: bool = False, dry_run: bool = False) -> SyncResult:
        """
        全量同步组 (创建组/添加/移除成员，可选删除组)
        
        Args:
            groups: 要同步的组列表
            members_map: 组成员映射 {groupName: [userName, ...]}
            allow_delete: 是否删除 IDC 中多余的组
            dry_run: 是否只预览不执行
        
        Returns:
            SyncResult 同步结果
        """
        return self._sync_groups_impl(groups, members_map, allow_delete=allow_delete, allow_remove_members=True, dry_run=dry_run)
    
    def _sync_groups_impl(self, groups: list[SCIMGroup], members_map: dict[str, list[str]] | None, allow_delete: bool, allow_remove_members: bool, dry_run: bool) -> SyncResult:
        """同步组实现"""
        result = SyncResult()
        members_map = members_map or {}
        
        # 获取 IDC 现有数据
        idc_groups = {g.displayName: g for g in self.list_groups()}
        idc_users = list(self.list_users())
        user_id_map = {u.userName: u.id for u in idc_users if u.id}
        id_to_name = {u.id: u.userName for u in idc_users if u.id}
        local_names = {g.displayName for g in groups}
        
        for group in groups:
            name = group.displayName
            
            # 解析本地成员
            local_member_ids: set[str] = set()
            skipped_members: list[str] = []
            for member_name in members_map.get(name, []):
                if member_name in user_id_map:
                    uid = user_id_map[member_name]
                    if uid:
                        local_member_ids.add(uid)
                else:
                    skipped_members.append(member_name)
            
            try:
                if name in idc_groups:
                    idc_group = idc_groups[name]
                    if not idc_group.id:
                        result.errors.append(f"{name}: 组 ID 为空")
                        continue
                    
                    # 获取当前成员
                    current_members: set[str] = set()
                    for uid in user_id_map.values():
                        if uid and self.is_user_in_group(idc_group.id, uid):
                            current_members.add(uid)
                    
                    to_add = local_member_ids - current_members
                    to_remove = current_members - local_member_ids if allow_remove_members else set()
                    
                    if not to_add and not to_remove:
                        result.unchanged.append(name)
                        if skipped_members:
                            result.details[name] = {"id": idc_group.id, "skipped": skipped_members}
                    else:
                        if not dry_run:
                            if to_add:
                                self.add_group_members(idc_group.id, list(to_add))
                            if to_remove:
                                self.remove_group_members(idc_group.id, list(to_remove))
                        
                        result.updated.append(name)
                        result.details[name] = {
                            "id": idc_group.id,
                            "added": [{"id": uid, "userName": id_to_name.get(uid, "?")} for uid in to_add],
                            "removed": [{"id": uid, "userName": id_to_name.get(uid, "?")} for uid in to_remove],
                            "skipped": skipped_members,
                        }
                else:
                    # 创建新组
                    if not dry_run:
                        new_group = self.create_group(group)
                        if new_group.id and local_member_ids:
                            self.add_group_members(new_group.id, list(local_member_ids))
                        
                        result.details[name] = {
                            "id": new_group.id,
                            "added": [{"id": uid, "userName": id_to_name.get(uid, "?")} for uid in local_member_ids],
                            "skipped": skipped_members,
                        }
                    else:
                        result.details[name] = {
                            "added": [{"id": uid, "userName": id_to_name.get(uid, "?")} for uid in local_member_ids],
                            "skipped": skipped_members,
                        }
                    result.created.append(name)
            except Exception as e:
                result.errors.append(f"{name}: {e}")
        
        # 删除多余组
        if allow_delete:
            for name, group in idc_groups.items():
                if name not in local_names and group.id:
                    try:
                        if not dry_run:
                            self.delete_group(group.id)
                        result.deleted.append(name)
                        result.details[name] = {"id": group.id}
                    except Exception as e:
                        result.errors.append(f"{name}: {e}")
        
        return result
    
    def list_group_members(self, group_id: str) -> list[SCIMUser]:
        """
        列出组成员
        
        AWS IDC 限制: GET /Groups 不返回 members，需要遍历用户查询
        """
        members = []
        for user in self.list_users():
            if user.id and self.is_user_in_group(group_id, user.id):
                members.append(user)
        return members
    
    def _diff_dict(self, local: dict, remote: dict) -> list[str]:
        """比较两个字典，返回变更的字段列表"""
        changed = []
        local = {k: v for k, v in local.items() if k not in ("id", "schemas", "meta")}
        remote = {k: v for k, v in remote.items() if k not in ("id", "schemas", "meta")}
        
        all_keys = set(local.keys()) | set(remote.keys())
        for key in all_keys:
            if local.get(key) != remote.get(key):
                changed.append(key)
        return changed
