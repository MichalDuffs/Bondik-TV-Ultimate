#!/usr/bin/env python3
"""Compatibility entry point for Bondík EPG maintenance planning.

The main implementation lives in ``_plan_epg_maintenance_core``.  This wrapper
adds one safety normalization: safe exact proposals may target stable channels
that do not have an ``epg`` block yet.  In that case we create the block in the
in-memory proposal before delegating to the original patch builder.
"""

from __future__ import annotations

import sys

import _plan_epg_maintenance_core as _core
from _plan_epg_maintenance_core import *  # noqa: F401,F403


_CORE_BUILD_PROPOSED_CHANNELS_TEXT = _core.build_proposed_channels_text


def _ensure_missing_epg_blocks(
    original_text: str,
    proposals: list[dict],
) -> str:
    """Add placeholder EPG blocks only where a safe proposal needs one."""

    if not proposals:
        return original_text

    lines = original_text.splitlines(keepends=True)

    for proposal in proposals:
        channel_id = str(proposal["channel_id"])
        id_markers = (
            f'  - id: "{channel_id}"',
            f"  - id: '{channel_id}'",
            f"  - id: {channel_id}",
        )

        channel_start = None
        channel_end = len(lines)

        for index, line in enumerate(lines):
            if line.rstrip("\r\n") in id_markers:
                channel_start = index
                break

        # Preserve the core implementation's existing "channel not found"
        # error instead of duplicating that validation here.
        if channel_start is None:
            continue

        for index in range(channel_start + 1, len(lines)):
            if lines[index].startswith("  - id: "):
                channel_end = index
                break

        if any(
            lines[index].rstrip("\r\n") == "    epg:"
            for index in range(channel_start + 1, channel_end)
        ):
            continue

        insertion_index = channel_end

        for index in range(channel_start + 1, channel_end):
            line = lines[index]
            if (
                line.startswith("    logo:")
                or line.startswith("    status:")
                or line.startswith("    metadata:")
            ):
                insertion_index = index
                break

        newline = (
            "\r\n"
            if lines[channel_start].endswith("\r\n")
            else "\n"
        )

        block = []

        if (
            insertion_index > channel_start
            and lines[insertion_index - 1].strip()
        ):
            block.append(newline)

        block.extend(
            [
                f"    epg:{newline}",
                f"      id: null{newline}",
                f"      source: null{newline}",
                f"      enabled: false{newline}",
            ]
        )

        if (
            insertion_index < len(lines)
            and lines[insertion_index].strip()
        ):
            block.append(newline)

        lines[insertion_index:insertion_index] = block

    return "".join(lines)


def build_proposed_channels_text(
    original_text: str,
    proposals: list[dict],
) -> str:
    """Apply safe proposals even when the channel has no EPG block yet."""

    normalized_text = _ensure_missing_epg_blocks(
        original_text,
        proposals,
    )

    return _CORE_BUILD_PROPOSED_CHANNELS_TEXT(
        normalized_text,
        proposals,
    )


# Functions imported from the core module (including build_proposed_patch and
# main) resolve globals in that module, so wire the fixed builder there too.
_core.build_proposed_channels_text = build_proposed_channels_text


if __name__ == "__main__":
    sys.exit(_core.main())
