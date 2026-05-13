"""Feishu cursor for incremental sync by Drive modified_time."""

from pydantic import Field

from ._base import BaseCursor


class FeishuCursor(BaseCursor):
    """Tracks the max Feishu Drive modified_time (Unix seconds) seen in a successful sync.

    Documents with modified_time <= this value skip content fetch on incremental runs.
    """

    last_max_modified_epoch: str = Field(
        default="",
        description="Max modified_time (seconds since epoch as string) from last completed pass",
    )
