"""
AWS IDC SCIM 数据模型

严格按照 AWS IDC SCIM 文档定义：
https://docs.aws.amazon.com/singlesignon/latest/developerguide/limitations.html

AWS IDC 限制：
- 多值属性只支持单值 (emails, phoneNumbers, addresses)
- 不支持: password, ims, photos, groups, entitlements, x509Certificates
- emails/phoneNumbers 不支持 display 子属性
- manager 不支持 displayName 子属性
- GET /Groups 不返回 members
"""

from dataclasses import dataclass, field
from enum import Enum


class SCIMValidationError(ValueError):
    """SCIM 数据验证错误"""
    pass


# ============ User 单值属性 ============

@dataclass
class SCIMName:
    """
    用户姓名 (name)
    
    支持的子属性:
    - familyName: Yes
    - givenName: Yes
    - middleName: Yes
    - honorificPrefix: Yes
    - honorificSuffix: Yes
    - formatted: Yes
    """
    familyName: str | None = None
    givenName: str | None = None
    middleName: str | None = None
    honorificPrefix: str | None = None
    honorificSuffix: str | None = None
    formatted: str | None = None
    
    def to_dict(self) -> dict:
        """只返回有值的字段"""
        d = {}
        if self.familyName is not None:
            d["familyName"] = self.familyName
        if self.givenName is not None:
            d["givenName"] = self.givenName
        if self.middleName is not None:
            d["middleName"] = self.middleName
        if self.honorificPrefix is not None:
            d["honorificPrefix"] = self.honorificPrefix
        if self.honorificSuffix is not None:
            d["honorificSuffix"] = self.honorificSuffix
        if self.formatted is not None:
            d["formatted"] = self.formatted
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMName":
        return cls(
            familyName=data.get("familyName"),
            givenName=data.get("givenName"),
            middleName=data.get("middleName"),
            honorificPrefix=data.get("honorificPrefix"),
            honorificSuffix=data.get("honorificSuffix"),
            formatted=data.get("formatted"),
        )


# ============ User 多值属性 (AWS IDC 只支持单值) ============

@dataclass
class SCIMEmail:
    """
    邮箱 (emails) - AWS IDC 只支持单个
    
    支持的子属性:
    - value: Yes
    - type: Yes
    - primary: Yes
    - display: No (不支持)
    """
    value: str
    type: str | None = None
    primary: bool | None = None
    
    def __post_init__(self):
        if not self.value:
            raise SCIMValidationError("email.value 是必填字段")
    
    def to_dict(self) -> dict:
        d = {"value": self.value}
        if self.type is not None:
            d["type"] = self.type
        if self.primary is not None:
            d["primary"] = self.primary
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMEmail":
        return cls(
            value=data.get("value", ""),
            type=data.get("type"),
            primary=data.get("primary"),
        )


@dataclass
class SCIMPhoneNumber:
    """
    电话 (phoneNumbers) - AWS IDC 只支持单个
    
    支持的子属性:
    - value: Yes
    - type: Yes
    - display: No (不支持)
    """
    value: str
    type: str | None = None
    
    def __post_init__(self):
        if not self.value:
            raise SCIMValidationError("phoneNumber.value 是必填字段")
    
    def to_dict(self) -> dict:
        d = {"value": self.value}
        if self.type is not None:
            d["type"] = self.type
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMPhoneNumber":
        return cls(
            value=data.get("value", ""),
            type=data.get("type"),
        )


@dataclass
class SCIMAddress:
    """
    地址 (addresses) - AWS IDC 只支持单个
    
    支持的子属性:
    - formatted: Yes
    - streetAddress: Yes
    - locality: Yes
    - region: Yes
    - postalCode: Yes
    - country: Yes (文档写 Country 但实际是 country)
    """
    formatted: str | None = None
    streetAddress: str | None = None
    locality: str | None = None
    region: str | None = None
    postalCode: str | None = None
    country: str | None = None
    
    def to_dict(self) -> dict:
        d = {}
        if self.formatted is not None:
            d["formatted"] = self.formatted
        if self.streetAddress is not None:
            d["streetAddress"] = self.streetAddress
        if self.locality is not None:
            d["locality"] = self.locality
        if self.region is not None:
            d["region"] = self.region
        if self.postalCode is not None:
            d["postalCode"] = self.postalCode
        if self.country is not None:
            d["country"] = self.country
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMAddress":
        return cls(
            formatted=data.get("formatted"),
            streetAddress=data.get("streetAddress"),
            locality=data.get("locality"),
            region=data.get("region"),
            postalCode=data.get("postalCode"),
            country=data.get("country"),
        )


@dataclass
class SCIMRole:
    """
    角色 (roles) - AWS IDC 支持
    """
    value: str
    type: str | None = None
    primary: bool | None = None
    
    def to_dict(self) -> dict:
        d = {"value": self.value}
        if self.type is not None:
            d["type"] = self.type
        if self.primary is not None:
            d["primary"] = self.primary
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMRole":
        return cls(
            value=data.get("value", ""),
            type=data.get("type"),
            primary=data.get("primary"),
        )


# ============ Enterprise User 扩展 ============

@dataclass
class SCIMManager:
    """
    经理引用 (manager)
    
    支持的子属性:
    - value: Yes
    - $ref: Yes
    - displayName: No (不支持)
    """
    value: str
    ref: str | None = None  # 对应 $ref
    
    def __post_init__(self):
        if not self.value:
            raise SCIMValidationError("manager.value 是必填字段")
    
    def to_dict(self) -> dict:
        d = {"value": self.value}
        if self.ref is not None:
            d["$ref"] = self.ref
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMManager":
        return cls(
            value=data.get("value", ""),
            ref=data.get("$ref"),
        )


@dataclass
class SCIMEnterpriseUser:
    """
    企业用户扩展 (urn:ietf:params:scim:schemas:extension:enterprise:2.0:User)
    
    支持的属性:
    - employeeNumber: Yes
    - costCenter: Yes
    - organization: Yes
    - division: Yes
    - department: Yes
    - manager: Yes (子属性: value, $ref; 不支持 displayName)
    """
    employeeNumber: str | None = None
    costCenter: str | None = None
    organization: str | None = None
    division: str | None = None
    department: str | None = None
    manager: SCIMManager | None = None
    
    def to_dict(self) -> dict:
        d = {}
        if self.employeeNumber is not None:
            d["employeeNumber"] = self.employeeNumber
        if self.costCenter is not None:
            d["costCenter"] = self.costCenter
        if self.organization is not None:
            d["organization"] = self.organization
        if self.division is not None:
            d["division"] = self.division
        if self.department is not None:
            d["department"] = self.department
        if self.manager is not None:
            d["manager"] = self.manager.to_dict()
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMEnterpriseUser":
        manager = None
        if data.get("manager"):
            manager = SCIMManager.from_dict(data["manager"])
        return cls(
            employeeNumber=data.get("employeeNumber"),
            costCenter=data.get("costCenter"),
            organization=data.get("organization"),
            division=data.get("division"),
            department=data.get("department"),
            manager=manager,
        )


# ============ User 资源 ============

ENTERPRISE_USER_SCHEMA = "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User"
USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"


@dataclass
class SCIMUser:
    """
    SCIM User 资源
    
    单值属性 (全部支持):
    - userName, displayName, nickName, profileUrl, title, userType
    - preferredLanguage, locale, timezone, active
    - name (子属性全部支持)
    - password: 不支持
    
    多值属性 (只支持单值):
    - emails: 支持 (type, value, primary; 不支持 display)
    - phoneNumbers: 支持 (type, value; 不支持 display)
    - addresses: 支持 (formatted, streetAddress, locality, region, postalCode, country)
    - roles: 支持
    - ims, photos, groups, entitlements, x509Certificates: 不支持
    """
    userName: str
    
    # 可选单值属性
    id: str | None = None
    externalId: str | None = None
    displayName: str | None = None
    nickName: str | None = None
    profileUrl: str | None = None
    title: str | None = None
    userType: str | None = None
    preferredLanguage: str | None = None
    locale: str | None = None
    timezone: str | None = None
    active: bool | None = None
    
    # name 复合属性
    name: SCIMName | None = None
    
    # 多值属性 (AWS IDC 只支持单值，用 list 保持 SCIM 兼容)
    emails: list[SCIMEmail] | None = None
    phoneNumbers: list[SCIMPhoneNumber] | None = None
    addresses: list[SCIMAddress] | None = None
    roles: list[SCIMRole] | None = None
    
    # 企业扩展
    enterprise: SCIMEnterpriseUser | None = None
    
    # 元数据 (只读)
    meta: dict | None = None
    
    # 内部标记，跳过验证（用于 from_dict）
    _skip_validation: bool = field(default=False, repr=False)
    
    def __post_init__(self):
        """验证必填字段和 AWS IDC 限制"""
        if self._skip_validation:
            return
        if not self.userName:
            raise SCIMValidationError("userName 是必填字段")
        if not self.emails:
            raise SCIMValidationError("emails 是必填字段")
        if len(self.emails) > 1:
            raise SCIMValidationError("emails 只能有一个值 (AWS IDC 限制)")
        if self.phoneNumbers and len(self.phoneNumbers) > 1:
            raise SCIMValidationError("phoneNumbers 只能有一个值 (AWS IDC 限制)")
        if self.addresses and len(self.addresses) > 1:
            raise SCIMValidationError("addresses 只能有一个值 (AWS IDC 限制)")
    
    def to_dict(self, include_id: bool = False, for_create: bool = False) -> dict:
        """
        转换为 API 请求格式
        
        Args:
            include_id: 是否包含 id (AWS IDC PUT 要求)
            for_create: 是否用于创建 (添加 schemas)
        """
        d: dict = {"userName": self.userName}
        
        # schemas
        if for_create:
            schemas = [USER_SCHEMA]
            if self.enterprise:
                schemas.append(ENTERPRISE_USER_SCHEMA)
            d["schemas"] = schemas
        
        # id
        if include_id and self.id is not None:
            d["id"] = self.id
        
        # 可选单值属性
        if self.externalId is not None:
            d["externalId"] = self.externalId
        if self.displayName is not None:
            d["displayName"] = self.displayName
        if self.nickName is not None:
            d["nickName"] = self.nickName
        if self.profileUrl is not None:
            d["profileUrl"] = self.profileUrl
        if self.title is not None:
            d["title"] = self.title
        if self.userType is not None:
            d["userType"] = self.userType
        if self.preferredLanguage is not None:
            d["preferredLanguage"] = self.preferredLanguage
        if self.locale is not None:
            d["locale"] = self.locale
        if self.timezone is not None:
            d["timezone"] = self.timezone
        if self.active is not None:
            d["active"] = self.active
        
        # name
        if self.name is not None:
            name_dict = self.name.to_dict()
            if name_dict:  # 只有非空才添加
                d["name"] = name_dict
        
        # 多值属性
        if self.emails:
            d["emails"] = [e.to_dict() for e in self.emails]
        if self.phoneNumbers:
            d["phoneNumbers"] = [p.to_dict() for p in self.phoneNumbers]
        if self.addresses:
            d["addresses"] = [a.to_dict() for a in self.addresses]
        if self.roles:
            d["roles"] = [r.to_dict() for r in self.roles]
        
        # 企业扩展
        if self.enterprise is not None:
            ent_dict = self.enterprise.to_dict()
            if ent_dict:  # 只有非空才添加
                d[ENTERPRISE_USER_SCHEMA] = ent_dict
        
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMUser":
        """从 API 响应解析"""
        # name
        name = None
        if data.get("name"):
            name = SCIMName.from_dict(data["name"])
        
        # emails
        emails = None
        if data.get("emails"):
            emails = [SCIMEmail.from_dict(e) for e in data["emails"]]
        
        # phoneNumbers
        phone_numbers = None
        if data.get("phoneNumbers"):
            phone_numbers = [SCIMPhoneNumber.from_dict(p) for p in data["phoneNumbers"]]
        
        # addresses
        addresses = None
        if data.get("addresses"):
            addresses = [SCIMAddress.from_dict(a) for a in data["addresses"]]
        
        # roles
        roles = None
        if data.get("roles"):
            roles = [SCIMRole.from_dict(r) for r in data["roles"]]
        
        # 企业扩展
        enterprise = None
        if data.get(ENTERPRISE_USER_SCHEMA):
            enterprise = SCIMEnterpriseUser.from_dict(data[ENTERPRISE_USER_SCHEMA])
        
        return cls(
            id=data.get("id"),
            userName=data.get("userName", ""),
            externalId=data.get("externalId"),
            displayName=data.get("displayName"),
            nickName=data.get("nickName"),
            profileUrl=data.get("profileUrl"),
            title=data.get("title"),
            userType=data.get("userType"),
            preferredLanguage=data.get("preferredLanguage"),
            locale=data.get("locale"),
            timezone=data.get("timezone"),
            active=data.get("active"),
            name=name,
            emails=emails,
            phoneNumbers=phone_numbers,
            addresses=addresses,
            roles=roles,
            enterprise=enterprise,
            meta=data.get("meta"),
            _skip_validation=True,  # API 响应不验证
        )


# ============ Group 资源 ============

@dataclass
class SCIMGroupMember:
    """
    组成员引用 (members)
    
    支持的子属性:
    - value: Yes
    - type: Yes
    - $ref: Yes
    - display: No (不支持)
    
    注意: GET /Groups 不返回 members
    """
    value: str
    type: str | None = None
    ref: str | None = None  # 对应 $ref
    
    def to_dict(self) -> dict:
        d = {"value": self.value}
        if self.type is not None:
            d["type"] = self.type
        if self.ref is not None:
            d["$ref"] = self.ref
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMGroupMember":
        return cls(
            value=data.get("value", ""),
            type=data.get("type"),
            ref=data.get("$ref"),
        )


@dataclass
class SCIMGroup:
    """
    SCIM Group 资源
    
    单值属性:
    - displayName: Yes
    
    多值属性:
    - members: Yes (但 GET 不返回)
      子属性: value, type, $ref (不支持 display)
    
    AWS IDC 限制:
    - GET /Groups 不返回 members
    - PUT 不支持 (501)，只能用 PATCH
    - PATCH 只支持 add/remove，不支持 replace
    """
    displayName: str
    id: str | None = None
    externalId: str | None = None
    members: list[SCIMGroupMember] | None = None
    meta: dict | None = None
    
    def __post_init__(self):
        if not self.displayName:
            raise SCIMValidationError("displayName 是必填字段")
    
    def to_dict(self, for_create: bool = False) -> dict:
        """转换为 API 请求格式"""
        d: dict = {"displayName": self.displayName}
        
        if for_create:
            d["schemas"] = [GROUP_SCHEMA]
        
        if self.externalId is not None:
            d["externalId"] = self.externalId
        
        # members 通常不在 create 中设置，而是用 PATCH
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> "SCIMGroup":
        """从 API 响应解析"""
        members = None
        if data.get("members"):
            members = [SCIMGroupMember.from_dict(m) for m in data["members"]]
        
        return cls(
            id=data.get("id"),
            displayName=data.get("displayName", ""),
            externalId=data.get("externalId"),
            members=members,
            meta=data.get("meta"),
        )


# ============ PATCH 操作 ============

class PatchOpType(str, Enum):
    """
    PATCH 操作类型
    
    AWS IDC 只支持 add/remove，不支持 replace
    """
    ADD = "add"
    REMOVE = "remove"


@dataclass
class PatchOperation:
    """单个 PATCH 操作"""
    op: PatchOpType | str
    path: str | None = None
    value: list | dict | str | None = None
    
    def to_dict(self) -> dict:
        d: dict = {"op": self.op.value if isinstance(self.op, PatchOpType) else self.op}
        if self.path is not None:
            d["path"] = self.path
        if self.value is not None:
            d["value"] = self.value
        return d


@dataclass
class PatchOp:
    """PATCH 请求体"""
    operations: list[PatchOperation]
    
    def to_dict(self) -> dict:
        return {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:PatchOp"],
            "Operations": [op.to_dict() for op in self.operations],
        }


# ============ 响应类型 ============

@dataclass
class ListResponse:
    """
    列表响应
    
    AWS IDC 使用 nextCursor 而非标准的 startIndex 分页
    """
    total_results: int
    resources: list[dict]
    next_cursor: str | None = None
    items_per_page: int | None = None
    start_index: int | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "ListResponse":
        # nextCursor 大小写兼容
        next_cursor = data.get("nextCursor") or data.get("nextcursor")
        # 空字符串视为 None
        if next_cursor == "":
            next_cursor = None
        
        return cls(
            total_results=data.get("totalResults", 0),
            resources=data.get("Resources", []),
            next_cursor=next_cursor,
            items_per_page=data.get("itemsPerPage"),
            start_index=data.get("startIndex"),
        )


@dataclass
class SCIMError:
    """
    SCIM 错误响应
    
    AWS IDC 会返回额外字段: exceptionrequestid, timestamp
    """
    status: int
    detail: str | None = None
    scim_type: str | None = None
    exception_request_id: str | None = None
    timestamp: str | None = None
    
    @classmethod
    def from_dict(cls, data: dict, status_code: int = 0) -> "SCIMError":
        return cls(
            status=data.get("status", status_code),
            detail=data.get("detail") or data.get("message"),
            scim_type=data.get("scimType"),
            exception_request_id=data.get("exceptionrequestid"),
            timestamp=data.get("timestamp"),
        )
    
    def __str__(self) -> str:
        msg = f"[{self.status}] {self.detail or 'Unknown error'}"
        if self.exception_request_id:
            msg += f" (request: {self.exception_request_id})"
        return msg



# ============ 同步结果 ============

@dataclass
class SyncResult:
    """同步操作结果"""
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)  # {name: {"added": [...], "removed": [...], ...}}
