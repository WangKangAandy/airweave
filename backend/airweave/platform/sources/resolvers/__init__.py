"""Shared source resolvers."""

from .base import BatchEntryResolver, BatchResolveResult
from .feishu import FeishuEntryResolver, ResolvedFeishuEntry

__all__ = [
    "BatchEntryResolver",
    "BatchResolveResult",
    "FeishuEntryResolver",
    "ResolvedFeishuEntry",
]
