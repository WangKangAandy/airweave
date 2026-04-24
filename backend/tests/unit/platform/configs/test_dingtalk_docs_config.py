"""Unit tests for DingtalkConfig constraints."""

import pytest
from pydantic import ValidationError

from airweave.platform.configs.config import DingtalkConfig


def test_links_priority_allows_empty_roots():
    """links can be primary entry without root IDs."""
    cfg = DingtalkConfig(
        links="doc:abc folder:def",
    )
    assert cfg.links == "doc:abc,folder:def"
    assert cfg.root_space_id == ""
    assert cfg.root_folder_id == ""
    assert cfg.operator_union_id == ""


def test_requires_links_when_no_hidden_root_fallback():
    """UI path requires links when hidden fallback IDs are absent."""
    with pytest.raises(ValidationError, match="Provide Dingtalk links"):
        DingtalkConfig(
            links="",
            root_space_id="",
            root_folder_id="",
        )


def test_rejects_both_root_space_and_folder_without_links():
    """root_space_id and root_folder_id cannot both be primary entries."""
    with pytest.raises(
        ValidationError,
        match="root_space_id and root_folder_id cannot both be primary entries",
    ):
        DingtalkConfig(
            links="",
            root_space_id="space-1",
            root_folder_id="folder-1",
        )

