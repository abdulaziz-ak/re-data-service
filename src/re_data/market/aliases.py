"""Alias maps and normalization helpers — copied from realestate-core-service/benchmarks.py.

These are the source-of-truth mappings for area/unit-type resolution used by
all market lookup and listing logic. benchmarks.py retains an identical copy
for parity tests; any future change must be made in both places.
"""

from __future__ import annotations

from re_data.ingest.parsers import norm as _norm  # re-export for market callers

__all__ = [
    "_norm",
    "_UNIT_TYPE_ALIASES",
    "_AREA_ALIASES",
    "_AREA_EMIRATE_MAP",
    "resolve_area_value",
]

# DLD CSV uses "flat" for what the UI/API callers call "apartment".
_UNIT_TYPE_ALIASES: dict[str, list[str]] = {
    "apartment": ["flat", "apartment"],
    "flat": ["flat", "apartment"],
    "villa": ["villa"],
    "townhouse": ["townhouse"],
    "penthouse": ["penthouse"],
    "studio": ["studio", "flat"],
}

# Common shorthand → DLD area name mappings (all lowercase, normalised)
_AREA_ALIASES: dict[str, str] = {
    "jvc": "jumeirah village circle",
    "jvt": "jumeirah village triangle",
    "jbr": "jumeirah beach residence",
    "marina": "dubai marina",
    "dubai marina": "dubai marina",
    "downtown": "downtown dubai",
    "downtown dubai": "downtown dubai",
    "jlt": "jumeirah lake towers",
    "difc": "dubai international financial centre",
    "dip": "dubai investment park",
    "dic": "dubai internet city",
    "dmc": "dubai media city",
    "dhcc": "dubai healthcare city",
    "impz": "international media production zone",
    "mbr": "mohammed bin rashid city",
    "mbrcity": "mohammed bin rashid city",
    "silicon oasis": "dubai silicon oasis",
    "dso": "dubai silicon oasis",
    "discovery gardens": "discovery gardens",
    "international city": "international city",
    "sport city": "dubai sports city",
    "sports city": "dubai sports city",
    "motor city": "motor city",
    "business bay": "business bay",
    "palm": "palm jumeirah",
    "palm jumeirah": "palm jumeirah",
    "the palm": "palm jumeirah",
    "the greens": "the greens",
    "greens": "the greens",
    "the views": "the views",
    "arabian ranches": "arabian ranches",
    "remraam": "remraam",
    "jumeirah": "jumeirah",
    "al barsha": "al barsha",
    "mirdif": "mirdif",
    "jumeirah islands": "jumeirah islands",
    "culture village": "culture village",
    "al furjan": "al furjan",
    "town square": "town square",
    "dubai hills": "dubai hills estate",
    "dubai hills estate": "dubai hills estate",
    "damac hills": "damac hills",
    "damac hills 2": "damac hills 2",
    "akoya": "damac hills 2",
    "ras al khaimah": "ras al khaimah",
    "rak": "ras al khaimah",
    "al marjan": "al marjan island",
    "al marjan island": "al marjan island",
}

# Maps each canonical area name to its emirate (lowercase).
# Areas not listed here default to "dubai".
_AREA_EMIRATE_MAP: dict[str, str] = {
    "al marjan island": "ras al khaimah",
    "ras al khaimah": "ras al khaimah",
}


def resolve_area_value(canonical: str) -> str:
    """Return the longest alias key that resolves to *canonical*, or *canonical* itself.

    This gives the most descriptive short-form key for frontend dropdowns
    (e.g. "jvc" for "jumeirah village circle").
    """
    best: str | None = None
    for alias_key, canon in _AREA_ALIASES.items():
        if canon == canonical:
            if best is None or len(alias_key) > len(best):
                best = alias_key
    return best if best is not None else canonical
