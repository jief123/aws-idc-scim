"""
AWS IDC SCIM Client

专为 AWS Identity Center SCIM 实现设计的 Python 客户端。
"""

from .models import (
    SCIMUser,
    SCIMGroup,
    SCIMName,
    SCIMEmail,
    SCIMPhoneNumber,
    SCIMAddress,
    SCIMRole,
    SCIMManager,
    SCIMEnterpriseUser,
    SCIMGroupMember,
    SCIMError,
    SCIMValidationError,
    PatchOp,
    PatchOperation,
    PatchOpType,
    ListResponse,
    SyncResult,
)

from .client import SCIMClient, SCIMClientError
from .filters import Filter

__all__ = [
    # Client
    "SCIMClient",
    "SCIMClientError",
    # Models
    "SCIMUser",
    "SCIMGroup",
    "SCIMName",
    "SCIMEmail",
    "SCIMPhoneNumber",
    "SCIMAddress",
    "SCIMRole",
    "SCIMManager",
    "SCIMEnterpriseUser",
    "SCIMGroupMember",
    "SCIMError",
    "SCIMValidationError",
    "PatchOp",
    "PatchOperation",
    "PatchOpType",
    "ListResponse",
    "SyncResult",
    # Filter
    "Filter",
]
