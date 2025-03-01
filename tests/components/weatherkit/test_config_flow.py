"""Test the Apple WeatherKit config flow."""
from unittest.mock import AsyncMock, patch

from apple_weatherkit import DataSetType
from apple_weatherkit.client import (
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientCommunicationError,
    WeatherKitApiClientError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.weatherkit.config_flow import (
    WeatherKitUnsupportedLocationError,
)
from homeassistant.components.weatherkit.const import (
    CONF_KEY_ID,
    CONF_KEY_PEM,
    CONF_SERVICE_ID,
    CONF_TEAM_ID,
    DOMAIN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import EXAMPLE_CONFIG_DATA

pytestmark = pytest.mark.usefixtures("mock_setup_entry")

EXAMPLE_USER_INPUT = {
    CONF_LOCATION: {
        CONF_LATITUDE: 35.4690101707532,
        CONF_LONGITUDE: 135.74817234593166,
    },
    CONF_KEY_ID: "QABCDEFG123",
    CONF_SERVICE_ID: "io.home-assistant.testing",
    CONF_TEAM_ID: "ABCD123456",
    CONF_KEY_PEM: "-----BEGIN PRIVATE KEY-----\nwhateverkey\n-----END PRIVATE KEY-----",
}


async def _test_exception_generates_error(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.weatherkit.config_flow.WeatherKitFlowHandler._test_config",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY

    location = EXAMPLE_USER_INPUT[CONF_LOCATION]
    assert result["title"] == f"{location[CONF_LATITUDE]}, {location[CONF_LONGITUDE]}"

    assert result["data"] == EXAMPLE_CONFIG_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (WeatherKitApiClientAuthenticationError, "invalid_auth"),
        (WeatherKitApiClientCommunicationError, "cannot_connect"),
        (WeatherKitUnsupportedLocationError, "unsupported_location"),
        (WeatherKitApiClientError, "unknown"),
    ],
)
async def test_error_handling(
    hass: HomeAssistant, exception: Exception, expected_error: str
) -> None:
    """Test that we handle various exceptions and generate appropriate errors."""
    await _test_exception_generates_error(hass, exception, expected_error)


async def test_form_unsupported_location(hass: HomeAssistant) -> None:
    """Test we handle when WeatherKit does not support the location."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_location"}

    # Test that we can recover from this error by changing the location
    with patch(
        "homeassistant.components.weatherkit.WeatherKitApiClient.get_availability",
        return_value=[DataSetType.CURRENT_WEATHER],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            EXAMPLE_USER_INPUT,
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
