"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

from pyrainbird import AvailableStations, RainbirdController
import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import ATTR_ENTITY_ID, CONF_FRIENDLY_NAME, CONF_TRIGGER_TIME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_ZONES, DATA_RAINBIRD, DOMAIN, RAINBIRD_CONTROLLER

ATTR_DURATION = "duration"

SERVICE_START_IRRIGATION = "start_irrigation"
SERVICE_TEST_IRRIGATION = "test_irrigation"
SERVICE_STOP_IRRIGATION = "stop_irrigation"
SERVICE_SET_RAIN_DELAY = "set_rain_delay"

SERVICE_SCHEMA_START_IRRIGATION = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DURATION): cv.positive_float,
    }
)

SERVICE_SCHEMA_TEST_IRRIGATION = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

SERVICE_SCHEMA_STOP_IRRIGATION = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)

SERVICE_SCHEMA_RAIN_DELAY = vol.Schema(
    {
        vol.Required(ATTR_DURATION): cv.positive_float,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Rain Bird switches over a Rain Bird controller."""

    if discovery_info is None:
        return

    controller: RainbirdController = hass.data[DATA_RAINBIRD][
        discovery_info[RAINBIRD_CONTROLLER]
    ]
    available_stations: AvailableStations = controller.get_available_stations()
    if not (available_stations and available_stations.stations):
        return
    devices = []
    for zone in range(1, available_stations.stations.count + 1):
        if available_stations.stations.active(zone):
            zone_config = discovery_info.get(CONF_ZONES, {}).get(zone, {})
            time = zone_config.get(CONF_TRIGGER_TIME, discovery_info[CONF_TRIGGER_TIME])
            name = zone_config.get(CONF_FRIENDLY_NAME)
            devices.append(
                RainBirdSwitch(
                    controller,
                    zone,
                    time,
                    name if name else f"Sprinkler {zone}",
                )
            )

    add_entities(devices, True)

    def start_irrigation(service: ServiceCall) -> None:
        entity_id = service.data[ATTR_ENTITY_ID]
        duration = service.data[ATTR_DURATION]

        for device in devices:
            if device.entity_id == entity_id:
                device.turn_on(duration=duration)

    hass.services.register(
        DOMAIN,
        SERVICE_START_IRRIGATION,
        start_irrigation,
        schema=SERVICE_SCHEMA_START_IRRIGATION,
    )

    def test_irrigation(service: ServiceCall) -> None:
        entity_id = service.data[ATTR_ENTITY_ID]

        for device in devices:
            if device.entity_id == entity_id:
                device.test_zone()

    hass.services.register(
        DOMAIN,
        SERVICE_TEST_IRRIGATION,
        test_irrigation,
        schema=SERVICE_SCHEMA_TEST_IRRIGATION,
    )

    def stop_irrigation(service: ServiceCall) -> None:
        entity_id = service.data[ATTR_ENTITY_ID]

        for device in devices:
            if device.entity_id == entity_id:
                device.turn_off()

    hass.services.register(
        DOMAIN,
        SERVICE_STOP_IRRIGATION,
        stop_irrigation,
        schema=SERVICE_SCHEMA_STOP_IRRIGATION,
    )

    def set_rain_delay(service: ServiceCall) -> None:
        duration = service.data[ATTR_DURATION]

        controller.set_rain_delay(duration)

    hass.services.register(
        DOMAIN,
        SERVICE_SET_RAIN_DELAY,
        set_rain_delay,
        schema=SERVICE_SCHEMA_RAIN_DELAY,
    )


class RainBirdSwitch(SwitchEntity):
    """Representation of a Rain Bird switch."""

    def __init__(self, controller: RainbirdController, zone, time, name):
        """Initialize a Rain Bird Switch Device."""
        self._rainbird = controller
        self._zone = zone
        self._name = name
        self._state = None
        self._duration = time
        self._attributes = {ATTR_DURATION: self._duration, "zone": self._zone}

    @property
    def extra_state_attributes(self):
        """Return state attributes."""
        return self._attributes

    @property
    def name(self):
        """Get the name of the switch."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn the switch on for time period."""
        if self._rainbird.irrigate_zone(
            int(self._zone),
            int(kwargs[ATTR_DURATION] if ATTR_DURATION in kwargs else self._duration),
        ):
            self._state = True

    def test_zone(self, **kwargs):
        """Turn the switch on."""
        if self._rainbird.test_zone(int(self._zone)):
            self._state = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        if self._rainbird.stop_irrigation():
            self._state = False

    def update(self):
        """Update switch status."""
        self._state = self._rainbird.get_zone_state(self._zone)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state
