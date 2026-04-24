"""Shared source resolvers."""

from .base import BatchEntryResolver, BatchResolveResult
from .dingtalk import DingTalkEntryResolver, ResolvedDingTalkEntry
from .feishu import FeishuEntryResolver, ResolvedFeishuEntry

__all__ = [
    "BatchEntryResolver",
    "BatchResolveResult",
    "DingTalkEntryResolver",
    "ResolvedDingTalkEntry",
    "FeishuEntryResolver",
    "ResolvedFeishuEntry",
]
