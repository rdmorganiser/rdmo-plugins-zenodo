import re


def is_edtf_l0_date(value: str) -> str:
    """
    Accepts EDTF Level 0 "Date" or "Date Interval":
      YYYY | YYYY-MM | YYYY-MM-DD
      YYYY/YYYY | YYYY-MM/YYYY-MM | YYYY-MM-DD/YYYY-MM-DD, etc.
    """
    if not re.match(r"^\d{4}(-\d{2}(-\d{2})?)?(/\d{4}(-\d{2}(-\d{2})?)?)?$", value):
        raise ValueError(f"Invalid EDTF Level 0 date {value!r}")
    return value

def is_iso_date(value: str) -> str:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        raise ValueError(f"Invalid ISO date {value!r}; must be YYYY-MM-DD")
    return value
