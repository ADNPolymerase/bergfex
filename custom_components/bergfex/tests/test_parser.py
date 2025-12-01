import pytest
from custom_components.bergfex.parser import (
    parse_overview_data,
    parse_resort_page,
    parse_snow_forecast_images,
)
from pathlib import Path
from datetime import datetime


def test_parse_snow_forecast_images():
    """Test parsing of snow forecast images."""
    html = """
    <div class="snowforecast-img">
        <a href="https://vcdn.bergfex.at/images/resized/8b/daily.jpg" data-caption="Daily Caption">
            <img src="..." alt="Daily Alt">
        </a>
    </div>
    <div class="snowforecast-img">
        <a href="https://vcdn.bergfex.at/images/resized/5d/12h.jpg" data-caption="12h Caption">
            <img src="..." alt="12h Alt">
        </a>
    </div>
    <div class="snowforecast-img">
        <a href="https://vcdn.bergfex.at/images/resized/7b/summary.jpg" data-caption="Summary Caption">
            <img src="..." alt="Summary Alt">
        </a>
    </div>
    """
    
    # Test page 0 (no summary expected, but if present it might be parsed if logic allows, 
    # but our logic checks page_num > 0 for summary)
    result_page_0 = parse_snow_forecast_images(html, 0)
    assert result_page_0["daily_forecast_url"] == "https://vcdn.bergfex.at/images/resized/8b/daily.jpg"
    assert result_page_0["daily_caption"] == "Daily Caption"
    assert "summary_url" not in result_page_0
    
    # Test page 1 (summary expected)
    result_page_1 = parse_snow_forecast_images(html, 1)
    assert result_page_1["daily_forecast_url"] == "https://vcdn.bergfex.at/images/resized/8b/daily.jpg"
    assert result_page_1["daily_caption"] == "Daily Caption"
    assert result_page_1["summary_url"] == "https://vcdn.bergfex.at/images/resized/7b/summary.jpg"
    assert result_page_1["summary_caption"] == "Summary Caption"


@pytest.fixture
def lelex_crozet_html():
    fixture_path = Path(__file__).parent / "fixtures" / "lelex-crozet.html"
    with open(fixture_path, "r") as f:
        return f.read()


def test_parse_lelex_crozet_snow_data(lelex_crozet_html):
    data = parse_resort_page(lelex_crozet_html)

    assert data["resort_name"] == "Lélex - Crozet"
    assert data["new_snow"] == "15"
    assert data["snow_mountain"] == "15"
    # Updated to expect timezone-aware datetime (Europe/Vienna)
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Vienna")
    expected_dt = datetime(2025, 11, 5, 14, 40, tzinfo=tz)
    assert data["snow_valley"] == "5"
    assert data["lifts_open_count"] == 8
    assert data["lifts_total_count"] == 10
    assert data["status"] == "Open"
    assert data["status"] == "Open"
    assert data["last_update"] == expected_dt
