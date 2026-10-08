# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Shared Unicode coverage policy for the pinned Hebrew font stack."""

HEBREW_ALLOWED = frozenset(
    cp for cp in range(0x0590, 0x0600)
    if not (
        cp == 0x0590
        or 0x0591 <= cp <= 0x05AF
        or cp == 0x05C6
        or 0x05C8 <= cp <= 0x05CF
        or 0x05C4 <= cp <= 0x05C5
        or 0x05EB <= cp <= 0x05EF
        or 0x05F5 <= cp <= 0x05FF
    )
)

# Precomposed Latin guaranteed by every effective pinned rm/sf stack. This
# covers Western- and common Central-European names with weight-matched
# fallbacks where a primary face lacks a codepoint.
LATIN_PRECOMPOSED_ALLOWED = frozenset(
    list(range(0x00C0, 0x0100))
    + list(range(0x0100, 0x0108))
    + list(range(0x010C, 0x0112))
    + list(range(0x0118, 0x011C))
    + list(range(0x0139, 0x013F))
    + list(range(0x0141, 0x0149))
    + list(range(0x0150, 0x015C))
    + list(range(0x0160, 0x0166))
    + list(range(0x016A, 0x017F))
)

LATIN_COMBINING_ALLOWED = frozenset({
    0x0300, 0x0301, 0x0302, 0x0303, 0x0304, 0x0306, 0x0307,
    0x0308, 0x030A, 0x030B, 0x030C, 0x0327, 0x0328,
})

TYPOGRAPHIC_ALLOWED = frozenset(map(ord, "–—…“”‘’־°₪"))
