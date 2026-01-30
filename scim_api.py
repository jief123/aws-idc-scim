#!/usr/bin/env python3
"""
AWS Identity Center SCIM REST API
"""
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from aws_idc_scim import (
    SCIMClient,
    SCIMClientError,
    SCIMUser,
    SCIMGroup,
    SCIMName,
    SCIMEmail,
    SCIMValidationError,
    PatchOperation,
)


def load_config():
    path = Path("scim-config.json")
    if not path.exists():
        raise RuntimeError("scim-config.json 不存在")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


app = FastAPI(title="AWS IDC SCIM API", version="1.0.0")


def get_client() -> SCIMClient:
    config = load_config()
    return SCIMClient(config["scim_endpoint"], config["scim_token"])


def build_user(data: dict) -> SCIMUser:
    """从 dict 构建 SCIMUser"""
    name = None
    if data.get("name"):
        name = SCIMName(
            familyName=data["name"].get("familyName"),
            givenName=data["name"].get("givenName"),
        )
    
    emails = None
    if data.get("emails"):
        emails = [SCIMEmail(
            value=e["value"],
            type=e.get("type"),
            primary=e.get("primary"),
        ) for e in data["emails"]]
    
    return SCIMUser(
        userName=data["userName"],
        displayName=data.get("displayName"),
        name=name,
        emails=emails,
        active=data.get("active"),
        title=data.get("title"),
        userType=data.get("userType"),
        externalId=data.get("externalId"),
    )


def user_to_dict(user: SCIMUser) -> dict:
    d = user.to_dict()
    d["id"] = user.id
    return d


# ========== 请求模型 ==========

class UserCreate(BaseModel):
    userName: str
    displayName: str
    name: dict
    emails: list[dict]
    active: bool = True
    title: str | None = None
    userType: str | None = None
    externalId: str | None = None


class GroupCreate(BaseModel):
    displayName: str


class MemberAction(BaseModel):
    userName: str


class SyncRequest(BaseModel):
    data: list[dict]
    dryRun: bool = False
    delete: bool = False


class BatchDeleteRequest(BaseModel):
    users: list[dict]


class BatchGroupMemberRequest(BaseModel):
    members: list[dict]


# ========== 用户 API ==========

@app.get("/users")
def list_users():
    """列出所有用户"""
    client = get_client()
    try:
        return [user_to_dict(u) for u in client.get_all_users()]
    finally:
        client.close()


@app.get("/users/{user_name}")
def get_user(user_name: str):
    """获取单个用户"""
    client = get_client()
    try:
        user = client.find_user_by_username(user_name)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户不存在: {user_name}")
        return user_to_dict(user)
    finally:
        client.close()


@app.post("/users")
def create_user(user: UserCreate):
    """创建用户"""
    client = get_client()
    try:
        scim_user = build_user(user.model_dump(exclude_none=True))
        result = client.create_user(scim_user)
        return user_to_dict(result)
    except (SCIMClientError, SCIMValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.put("/users/{user_name}")
def update_user(user_name: str, user: UserCreate):
    """更新用户"""
    client = get_client()
    try:
        existing = client.find_user_by_username(user_name)
        if not existing or not existing.id:
            raise HTTPException(status_code=404, detail=f"用户不存在: {user_name}")
        
        data = user.model_dump(exclude_none=True)
        data["userName"] = user_name
        scim_user = build_user(data)
        user_dict = scim_user.to_dict()
        
        operations = []
        for key, value in user_dict.items():
            if key not in ("id", "schemas", "meta"):
                operations.append(PatchOperation(op="replace", path=key, value=value))
        
        client.patch_user(existing.id, operations)
        updated = client.find_user_by_username(user_name)
        return user_to_dict(updated) if updated else {}
    except (SCIMClientError, SCIMValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.delete("/users/{user_name}")
def delete_user(user_name: str):
    """删除用户"""
    client = get_client()
    try:
        user = client.find_user_by_username(user_name)
        if not user or not user.id:
            raise HTTPException(status_code=404, detail=f"用户不存在: {user_name}")
        client.delete_user(user.id)
        return {"message": f"已删除: {user_name}"}
    except SCIMClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.post("/users/sync")
def sync_users(req: SyncRequest):
    """增量同步用户（只添加/更新）"""
    client = get_client()
    try:
        users = [build_user(u) for u in req.data]
        result = client.sync_users(users, dry_run=req.dryRun)
        return {
            "created": result.created,
            "updated": result.updated,
            "unchanged": result.unchanged,
            "errors": result.errors,
            "details": result.details,
        }
    finally:
        client.close()


@app.post("/users/full-sync")
def full_sync_users(req: SyncRequest):
    """全量同步用户（添加/更新，可选删除）"""
    client = get_client()
    try:
        users = [build_user(u) for u in req.data]
        result = client.full_sync_users(users, allow_delete=req.delete, dry_run=req.dryRun)
        return {
            "created": result.created,
            "updated": result.updated,
            "deleted": result.deleted,
            "unchanged": result.unchanged,
            "errors": result.errors,
            "details": result.details,
        }
    finally:
        client.close()



# ========== 组 API ==========

@app.get("/groups")
def list_groups():
    """列出所有组"""
    client = get_client()
    try:
        return [{"id": g.id, "displayName": g.displayName} for g in client.get_all_groups()]
    finally:
        client.close()


@app.post("/groups")
def create_group(group: GroupCreate):
    """创建组"""
    client = get_client()
    try:
        result = client.create_group(SCIMGroup(displayName=group.displayName))
        return {"id": result.id, "displayName": result.displayName}
    except SCIMClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.delete("/groups/{group_name}")
def delete_group(group_name: str):
    """删除组"""
    client = get_client()
    try:
        group = client.find_group_by_name(group_name)
        if not group or not group.id:
            raise HTTPException(status_code=404, detail=f"组不存在: {group_name}")
        client.delete_group(group.id)
        return {"message": f"已删除: {group_name}"}
    except SCIMClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.get("/groups/{group_name}/members")
def list_group_members(group_name: str):
    """列出组成员"""
    client = get_client()
    try:
        group = client.find_group_by_name(group_name)
        if not group or not group.id:
            raise HTTPException(status_code=404, detail=f"组不存在: {group_name}")
        members = client.list_group_members(group.id)
        return [{"id": m.id, "userName": m.userName, "displayName": m.displayName} for m in members]
    except SCIMClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.post("/groups/{group_name}/members")
def add_group_member(group_name: str, member: MemberAction):
    """添加组成员"""
    client = get_client()
    try:
        group = client.find_group_by_name(group_name)
        if not group or not group.id:
            raise HTTPException(status_code=404, detail=f"组不存在: {group_name}")
        
        user = client.find_user_by_username(member.userName)
        if not user or not user.id:
            raise HTTPException(status_code=404, detail=f"用户不存在: {member.userName}")
        
        client.add_group_members(group.id, [user.id])
        return {"userId": user.id, "userName": member.userName, "groupName": group_name}
    except SCIMClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.delete("/groups/{group_name}/members/{user_name}")
def remove_group_member(group_name: str, user_name: str):
    """移除组成员"""
    client = get_client()
    try:
        group = client.find_group_by_name(group_name)
        if not group or not group.id:
            raise HTTPException(status_code=404, detail=f"组不存在: {group_name}")
        
        user = client.find_user_by_username(user_name)
        if not user or not user.id:
            raise HTTPException(status_code=404, detail=f"用户不存在: {user_name}")
        
        client.remove_group_members(group.id, [user.id])
        return {"message": f"已从 {group_name} 移除 {user_name}"}
    except SCIMClientError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        client.close()


@app.post("/groups/sync")
def sync_groups(req: SyncRequest):
    """增量同步组（只添加成员）"""
    client = get_client()
    try:
        groups = []
        members_map = {}
        for g in req.data:
            name = g["displayName"]
            groups.append(SCIMGroup(displayName=name))
            members = []
            for m in g.get("members", []):
                member_name = m.get("value") if isinstance(m, dict) else m
                if member_name:
                    members.append(member_name)
            members_map[name] = members
        
        result = client.sync_groups(groups, members_map, dry_run=req.dryRun)
        return {
            "created": result.created,
            "updated": result.updated,
            "unchanged": result.unchanged,
            "errors": result.errors,
            "details": result.details,
        }
    finally:
        client.close()


@app.post("/groups/full-sync")
def full_sync_groups(req: SyncRequest):
    """全量同步组（添加/移除成员，可选删除组）"""
    client = get_client()
    try:
        groups = []
        members_map = {}
        for g in req.data:
            name = g["displayName"]
            groups.append(SCIMGroup(displayName=name))
            members = []
            for m in g.get("members", []):
                member_name = m.get("value") if isinstance(m, dict) else m
                if member_name:
                    members.append(member_name)
            members_map[name] = members
        
        result = client.full_sync_groups(groups, members_map, allow_delete=req.delete, dry_run=req.dryRun)
        return {
            "created": result.created,
            "updated": result.updated,
            "deleted": result.deleted,
            "unchanged": result.unchanged,
            "errors": result.errors,
            "details": result.details,
        }
    finally:
        client.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
