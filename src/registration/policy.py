"""Shared registration policy for clouds and their landmark coordinates."""
from __future__ import annotations

import re

IDENTITY_MATRIX = "1 0 0 0\n0 1 0 0\n0 0 1 0\n0 0 0 1\n"


def registration_action(config: dict, filename: str) -> str:
    mode = config.get("mode", "all")
    if mode not in {"all", "gallery_only", "none"}:
        raise ValueError("Registration mode must be all, gallery_only, or none.")
    if mode == "none":
        return "bypassed"
    if mode == "gallery_only":
        if not re.fullmatch(config["gallery_filename_regex"], filename):
            return "bypassed"
        if config.get("reuse_gallery_root"):
            return "reused"
    return "registered"
