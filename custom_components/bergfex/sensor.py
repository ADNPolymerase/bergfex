import logging
from datetime import datetime, timedelta
from typing import Any, cast
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BASE_URL,
    CONF_COUNTRY,
    CONF_SKI_AREA,
    COORDINATORS,
    COUNTRIES,
    DOMAIN,
)
from .parser import parse_overview_data, parse_resort_page

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(minutes=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer l’entrée des capteurs Bergfex."""

    coordinator = entry.runtime_data
    _LOGGER.debug(
        "Sensor async_setup_entry - Coordinateur : %s, Données runtime de l’entrée : %s",
        coordinator,
        entry.runtime_data,
    )

    sensors = [
        BergfexSensor(coordinator, entry, "Statut", "status", icon="mdi:ski"),
        BergfexSensor(
            coordinator,
            entry,
            "Neige en vallée",
            "snow_valley",
            icon="mdi:snowflake",
            unit="cm",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Neige en montagne",
            "snow_mountain",
            icon="mdi:snowflake",
            unit="cm",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Neige fraîche",
            "new_snow",
            icon="mdi:weather-snowy-heavy",
            unit="cm",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "État de la neige",
            "snow_condition",
            icon="mdi:snowflake-alert",
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Dernière chute de neige",
            "last_snowfall",
            icon="mdi:calendar-clock",
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Risque d’avalanche",
            "avalanche_warning",
            icon="mdi:alert-octagon",
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Remontées ouvertes",
            "lifts_open_count",
            icon="mdi:gondola",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Remontées totales",
            "lifts_total_count",
            icon="mdi:map-marker-distance",
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Pistes ouvertes (km)",
            "slopes_open_km",
            icon="mdi:ski",
            unit="km",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Pistes totales (km)",
            "slopes_total_km",
            icon="mdi:ski",
            unit="km",
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Pistes ouvertes",
            "slopes_open_count",
            icon="mdi:ski",
            state_class=SensorStateClass.MEASUREMENT,
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Pistes totales",
            "slopes_total_count",
            icon="mdi:ski",
        ),
        BergfexSensor(
            coordinator,
            entry,
            "État des pistes",
            "slope_condition",
            icon="mdi:snowflake-variant",
        ),
        BergfexSensor(
            coordinator,
            entry,
            "Dernière mise à jour",
            "last_update",
            icon="mdi:clock-outline",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
    ]

    async_add_entities(sensors)


class BergfexSensor(SensorEntity):
    """Représentation d’un capteur Bergfex."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_name: str,
        data_key: str,
        icon: str | None = None,
        unit: str | None = None,
        state_class: SensorStateClass | None = None,
        device_class: SensorDeviceClass | None = None,
    ):
        """Initialisation du capteur."""
        self.coordinator = coordinator
        self._initial_area_name = entry.data["name"]  # Nom initial comme repli
        self._area_name = self._initial_area_name
        self._area_path = entry.data[CONF_SKI_AREA]
        self._config_url = urljoin(BASE_URL, self._area_path)
        self._sensor_name = sensor_name
        self._data_key = data_key
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class

        self._attr_unique_id = (
            f"bergfex_{self._initial_area_name.lower().replace(' ', '_')}_"
            f"{self._sensor_name.lower().replace(' ', '_')}"
        )
        self._attr_name = f"{self._initial_area_name} {self._sensor_name}"

        _LOGGER.debug(
            "BergfexSensor __init__ - Chemin station : %s, Nom initial : %s, "
            "ID unique : %s, Nom : %s",
            self._area_path,
            self._initial_area_name,
            self._attr_unique_id,
            self._attr_name,
        )

    def _update_names(self) -> None:
        """Met à jour le nom de la station, l’ID unique et le nom de l’entité."""
        if self.coordinator.data and self._area_path in self.coordinator.data:
            area_data = self.coordinator.data[self._area_path]
            self._area_name = area_data.get("resort_name", self._initial_area_name)
        else:
            self._area_name = self._initial_area_name

        self._attr_unique_id = (
            f"bergfex_{self._area_path.replace('/', '_')}_"
            f"{self._sensor_name.lower().replace(' ', '_')}"
        )
        self._attr_name = f"{self._area_name} {self._sensor_name}"

        _LOGGER.debug(
            "BergfexSensor _update_names - Données coordinateur : %s, "
            "Chemin station : %s, Nom station : %s",
            self.coordinator.data,
            self._area_path,
            self._area_name,
        )

    @property
    def native_value(self) -> str | int | datetime | None:
        """Retourne l’état du capteur."""
        if self.coordinator.data is None:
            return None

        all_areas_data = cast(dict, self.coordinator.data)
        area_data = all_areas_data.get(self._area_path)

        if area_data and self._data_key in area_data:
            value = area_data[self._data_key]

            if isinstance(value, datetime):
                return value

            if isinstance(value, str):
                if value.isdigit():
                    return int(value)
                try:
                    return float(value)
                except ValueError:
                    pass

            return value

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Retourne les attributs supplémentaires du capteur."""
        if self._data_key == "status":
            return {"lien": self._config_url}

        if self.coordinator.data and self._area_path in self.coordinator.data:
            area_data = self.coordinator.data[self._area_path]

            if self._data_key == "snow_mountain" and "elevation_mountain" in area_data:
                return {"altitude": area_data["elevation_mountain"]}

            if self._data_key == "snow_valley" and "elevation_valley" in area_data:
                return {"altitude": area_data["elevation_valley"]}

        return None

    @property
    def available(self) -> bool:
        """Indique si l’entité est disponible."""
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        """Retourne les informations de l’appareil."""
        return {
            "identifiers": {(DOMAIN, self._area_path)},
            "name": self._area_name,
            "manufacturer": "Bergfex",
            "model": "Station de ski",
            "configuration_url": self._config_url,
        }

    async def async_added_to_hass(self) -> None:
        """Appelé lorsque l’entité est ajoutée à Home Assistant."""
        self._update_names()
        self.async_on_remove(
            self.coordinator.async_add_listener(
                lambda: self.hass.async_create_task(self._handle_coordinator_update())
            )
        )

    async def _handle_coordinator_update(self) -> None:
        """Gère la mise à jour des données du coordinateur."""
        self._update_names()
        self.async_write_ha_state()
