"""Parse data from Bergfex (.fr / .com / .at)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LANGUAGE LABELS
# ---------------------------------------------------------------------------

LABELS = {
    "snow_condition": [
        "État de la neige",
        "Snow condition",
        "Schneezustand",
    ],
    "last_snowfall": [
        "Dernière chute de neige Région",
        "Latest snowfall Region",
        "Letzter Schneefall",
    ],
    "avalanche_warning": [
        "Niveau d’alerte avalanches",
        "Avalanche alert level",
        "Lawinenwarnstufe",
    ],
    "lifts": [
        "Remontées ouvertes",
        "Open lifts",
        "Offene Lifte",
    ],
    "slopes": [
        "Pistes ouvertes",
        "Open pistes",
        "Offene Pisten",
    ],
    "slope_condition": [
        "État de la piste",
        "Piste conditions",
        "Pistenzustand",
    ],
    "mountain": ["Sommet", "Mountain", "Berg"],
    "valley": ["Vallée", "Valley", "Tal"],
    "snow_height": ["Hauteur de neige", "Snow depth", "Schneehöhe"],
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_text_for_labels(soup: BeautifulSoup, labels: list[str]) -> str | None:
    """Return dd text for the first matching dt label."""
    for label in labels:
        dt = soup.find("dt", string=lambda t: t and label in t)
        if dt and (dd := dt.find_next_sibling("dd")):
            return dd.text.strip()
    return None


# ---------------------------------------------------------------------------
# DATETIME PARSER (FR / EN / DE)
# ---------------------------------------------------------------------------

def parse_bergfex_datetime(date_str: str) -> datetime | None:
    """Parse date strings from bergfex.fr / .com / .at."""
    if not date_str:
        return None

    date_str = date_str.strip().lower()

    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # type: ignore

    tz = ZoneInfo("Europe/Paris")
    now = datetime.now(tz)

    # Today
    if date_str.startswith(("aujourd", "today", "heute")):
        if m := re.search(r"(\d{1,2}):(\d{2})", date_str):
            return now.replace(
                hour=int(m.group(1)),
                minute=int(m.group(2)),
                second=0,
                microsecond=0,
            )

    # Yesterday
    if date_str.startswith(("hier", "yesterday", "gestern")):
        if m := re.search(r"(\d{1,2}):(\d{2})", date_str):
            y = now - timedelta(days=1)
            return y.replace(
                hour=int(m.group(1)),
                minute=int(m.group(2)),
                second=0,
                microsecond=0,
            )

    # dd.mm.(yyyy), hh:mm
    m = re.search(
        r"(\d{1,2})\.(\d{1,2})\.(?:\s*(\d{4}))?(?:,|\.)?\s*(\d{1,2}):(\d{2})",
        date_str,
    )
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        hour, minute = int(m.group(4)), int(m.group(5))

        try:
            result = datetime(year, month, day, hour, minute, tzinfo=tz)
            if not m.group(3) and result > now + timedelta(days=180):
                result = result.replace(year=year - 1)
            return result
        except ValueError:
            pass

    _LOGGER.debug("Could not parse date: %s", date_str)
    return None


# ---------------------------------------------------------------------------
# RESORT PAGE PARSER
# ---------------------------------------------------------------------------

def parse_resort_page(html: str) -> dict[str, Any]:
    """Parse a single resort page (schneebericht)."""
    soup = BeautifulSoup(html, "lxml")
    data: dict[str, Any] = {}

    # Resort name
    if h1 := soup.find("h1"):
        data["resort_name"] = h1.text.strip()

    # Snow depths & elevations
    for dt in soup.find_all("dt", class_="big"):
        text = dt.text.strip()

        if any(k in text for k in LABELS["mountain"]):
            if dd := dt.find_next_sibling("dd", class_="big"):
                data["snow_mountain"] = dd.text.replace("cm", "").strip()

        if any(k in text for k in LABELS["valley"]):
            if dd := dt.find_next_sibling("dd", class_="big"):
                data["snow_valley"] = dd.text.replace("cm", "").strip()

        if any(k in text for k in LABELS["snow_height"]):
            if "snow_valley" not in data:
                if dd := dt.find_next_sibling("dd", class_="big"):
                    data["snow_valley"] = dd.text.replace("cm", "").strip()

    # Textual info
    if v := get_text_for_labels(soup, LABELS["snow_condition"]):
        data["snow_condition"] = v

    if v := get_text_for_labels(soup, LABELS["last_snowfall"]):
        data["last_snowfall"] = v

    if v := get_text_for_labels(soup, LABELS["avalanche_warning"]):
        data["avalanche_warning"] = v.replace("Lawinenwarndienst", "").strip()

    # Lifts
    if v := get_text_for_labels(soup, LABELS["lifts"]):
        if "von" in v or "of" in v:
            parts = re.split(r"von|of", v)
            try:
                data["lifts_open_count"] = int(parts[0].strip())
                data["lifts_total_count"] = int(parts[1].strip().split()[0])
            except Exception:
                _LOGGER.debug("Lift parse error: %s", v)

    # Slopes
    if v := get_text_for_labels(soup, LABELS["slopes"]):
        if "km" in v:
            nums = re.findall(r"[\d,.]+", v)
            if len(nums) >= 1:
                data["slopes_open_km"] = float(nums[0].replace(",", "."))
            if len(nums) >= 2:
                data["slopes_total_km"] = float(nums[1].replace(",", "."))
        else:
            nums = re.findall(r"\d+", v)
            if len(nums) >= 1:
                data["slopes_open_count"] = int(nums[0])
            if len(nums) >= 2:
                data["slopes_total_count"] = int(nums[1])

    # Slope condition
    if v := get_text_for_labels(soup, LABELS["slope_condition"]):
        data["slope_condition"] = v

    # Last update
    if sub := soup.find("div", class_="h2-sub"):
        if dt := parse_bergfex_datetime(sub.text.strip()):
            data["last_update"] = dt

    # Status
    data["status"] = (
        "Open" if data.get("lifts_open_count", 0) > 0 else "Closed"
    )

    return {k: v for k, v in data.items() if v not in ("", "-", None)}
