"""Parse data from Bergfex."""

from __future__ import annotations

import logging
from typing import Any

from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


def parse_overview_data(html: str) -> dict[str, dict[str, Any]]:
    """Parse the HTML of the overview page and return a dict of all ski areas."""
    soup = BeautifulSoup(html, "lxml")
    results = {}

    table = soup.find("table", class_="snow")
    if not table:
        _LOGGER.warning("Could not find overview data table with class 'snow'")
        return {}

    for row in table.find_all("tr")[1:]:  # Skip header row
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        link = cols[0].find("a")
        if not (link and link.get("href")):
            continue

        area_path = link["href"]
        area_data = {}

        # Snow Depths (Valley, Mountain) and New Snow from data-value
        area_data["snow_valley"] = cols[1].get("data-value")
        area_data["snow_mountain"] = cols[2].get("data-value")
        area_data["new_snow"] = cols[3].get("data-value")

        # Lifts and Status (from column 4)
        lifts_cell = cols[4]
        status_div = lifts_cell.find("div", class_="icon-status")
        if status_div:
            classes = status_div.get("class", [])
            if "icon-status1" in classes:
                area_data["status"] = "Open"
            elif "icon-status0" in classes:
                area_data["status"] = "Closed"
            else:
                area_data["status"] = "Unknown"

        lifts_raw = lifts_cell.text.strip()
        lifts_open = None
        lifts_total = None

        if "/" in lifts_raw:
            parts = lifts_raw.split("/")
            if len(parts) == 2:
                try:
                    lifts_open = int(parts[0].strip())
                except ValueError:
                    _LOGGER.debug(
                        "Could not parse lifts_open_count: %s", parts[0].strip()
                    )
                try:
                    lifts_total = int(parts[1].strip())
                except ValueError:
                    _LOGGER.debug(
                        "Could not parse lifts_total_count: %s", parts[1].strip()
                    )
        elif lifts_raw.isdigit():
            try:
                lifts_open = int(lifts_raw)
            except ValueError:
                _LOGGER.debug("Could not parse lifts_open_count: %s", lifts_raw)

        if lifts_open is not None:
            area_data["lifts_open_count"] = lifts_open
        if lifts_total is not None:
            area_data["lifts_total_count"] = lifts_total

        # Last Update - Get timestamp from data-value on the <td> if available
        if "data-value" in cols[5].attrs:
            area_data["last_update"] = cols[5]["data-value"]
        else:
            area_data["last_update"] = cols[5].text.strip()  # Fallback to text

        # Clean up "-" values
        results[area_path] = {k: v for k, v in area_data.items() if v not in ("-", "")}

    return results


def get_text_from_dd(soup: BeautifulSoup, text: str) -> str | None:
    """Get the text from a dd element based on the text of the preceding dt element."""
    dt = soup.find("dt", string=lambda t: t and text in t)
    if dt and (dd := dt.find_next_sibling("dd")):
        return dd.text.strip()
    return None


def parse_resort_page(html: str) -> dict[str, Any]:
    """Parse the HTML of a single resort page."""
    soup = BeautifulSoup(html, "lxml")
    area_data = {}

    # Resort Name
    h1_tag = soup.find("h1", class_="tw-text-4xl")
    if h1_tag:
        spans = h1_tag.find_all("span")
        if len(spans) > 1:
            area_data["resort_name"] = spans[1].text.strip()

    # Snow depths
    all_big_dts = soup.find_all("dt", class_="big")
    for dt in all_big_dts:
        if "Berg" in dt.text:
            if dd := dt.find_next_sibling("dd", class_="big"):
                area_data["snow_mountain"] = dd.text.strip().replace("cm", "").strip()
        elif "Tal" in dt.text:
            if dd := dt.find_next_sibling("dd", class_="big"):
                area_data["snow_valley"] = dd.text.strip().replace("cm", "").strip()

    # Last update
    h2_sub = soup.find("div", class_="h2-sub")
    if h2_sub:
        area_data["last_update"] = h2_sub.text.strip()

    # Lifts
    lifts_text = get_text_from_dd(soup, "Offene Lifte")
    if lifts_text and "von" in lifts_text:
        parts = lifts_text.split("von")
        if len(parts) == 2:
            try:
                area_data["lifts_open_count"] = int(parts[0].strip())
                area_data["lifts_total_count"] = int(
                    parts[1].strip().split(" ")[0].strip()
                )
            except ValueError:
                _LOGGER.debug("Could not parse lifts: %s", lifts_text)

    # New snow
    new_snow_div = soup.find("div", class_="heading heading-ne desktop-only")
    if new_snow_div and (h1_div := new_snow_div.find("div", class_="h1")):
        area_data["new_snow"] = (
            h1_div.find("span").text.strip().replace("cm", "").strip()
        )

    # Status
    if area_data.get("lifts_open_count", 0) > 0:
        area_data["status"] = "Open"
    else:
        area_data["status"] = "Closed"

    return {k: v for k, v in area_data.items() if v not in ("-", "")}
