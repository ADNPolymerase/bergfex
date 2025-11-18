import pytest
from custom_components.bergfex.parser import parse_resort_page
from pathlib import Path


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
    assert data["snow_valley"] == "5"
    assert data["lifts_open_count"] == 8
    assert data["lifts_total_count"] == 10
    assert data["status"] == "Open"
    assert data["last_update"] == "05.11.2025, 14:40"
