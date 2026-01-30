"""
SCIM Filter 构建器

AWS IDC 只支持 eq 和 and 操作符，不支持 co/sw/or 等。
此模块提供类型安全的 filter 构建。
"""

from dataclasses import dataclass
from typing import Self


@dataclass
class FilterExpression:
    """Filter 表达式"""
    expression: str
    
    def __and__(self, other: "FilterExpression") -> "FilterExpression":
        """组合两个 filter (and)"""
        return FilterExpression(f"({self.expression}) and ({other.expression})")
    
    def __str__(self) -> str:
        return self.expression


class Filter:
    """
    SCIM Filter 构建器
    
    AWS IDC 只支持:
    - eq: 等于
    - and: 逻辑与
    
    不支持: co, sw, pr, gt, ge, lt, le, ne, or, not
    
    示例:
        >>> Filter.eq("userName", "test@example.com")
        'userName eq "test@example.com"'
        
        >>> Filter.eq("displayName", "Test") & Filter.eq("active", True)
        '(displayName eq "Test") and (active eq true)'
        
        >>> Filter.member_eq("userId123")
        'members.value eq "userId123"'
    """
    
    @staticmethod
    def eq(attr: str, value: str | bool) -> FilterExpression:
        """
        等于操作符
        
        Args:
            attr: 属性名
            value: 值 (字符串会自动加引号)
        """
        if isinstance(value, bool):
            val_str = "true" if value else "false"
        else:
            val_str = f'"{value}"'
        return FilterExpression(f'{attr} eq {val_str}')
    
    @staticmethod
    def member_eq(user_id: str) -> FilterExpression:
        """
        查询组成员
        
        用于查询用户所属的组，因为 GET /Groups 不返回 members
        
        Args:
            user_id: 用户 ID
        """
        return Filter.eq("members.value", user_id)
    
    @staticmethod
    def user_name(username: str) -> FilterExpression:
        """按 userName 过滤"""
        return Filter.eq("userName", username)
    
    @staticmethod
    def display_name(name: str) -> FilterExpression:
        """按 displayName 过滤"""
        return Filter.eq("displayName", name)
    
    @staticmethod
    def external_id(external_id: str) -> FilterExpression:
        """按 externalId 过滤"""
        return Filter.eq("externalId", external_id)
    
    @staticmethod
    def active(is_active: bool = True) -> FilterExpression:
        """按 active 状态过滤"""
        return Filter.eq("active", is_active)
