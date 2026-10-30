import asyncio
import logging
from time import time

import pytest

# from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from custom_components.tuya_local.const import CONF_DEVICE_ID, DOMAIN
from custom_components.tuya_local.device import TuyaLocalDevice, async_delete_device

from .const import EUROM_600_HEATER_PAYLOAD


@pytest.fixture
def mock_api(mocker):
    mock = mocker.patch("tinytuya.Device")
    mock.parent = None
    yield mock


@pytest.fixture
def patched_hass(hass, mocker):
    hass.is_running = True
    hass.is_stopping = False
    hass.data = {"tuya_local": {}}

    async def job(func, *args):
        print(f"{args}")
        return func(*args)

    mocker.patch.object(hass, "async_add_executor_job", side_effect=job)
    mocker.patch.object(hass, "async_create_task")
    return hass


@pytest.fixture
def subject(patched_hass, mock_api, mocker):
    subject = TuyaLocalDevice(
        "Some name",
        "some_dev_id",
        "some.ip.address",
        "some_local_key",
        "auto",
        None,
        patched_hass,
    )
    # For most tests we want the protocol working
    subject._api_protocol_version_index = 0
    subject._api_protocol_working = True
    subject._protocol_configured = "auto"
    return subject


def test_name(subject):
    """Returns the name given at instantiation."""
    assert subject.name == "Some name"


def test_unique_id(subject, mock_api):
    """Returns the unique ID presented by the API class."""
    assert subject.unique_id is mock_api().id


def test_subdevice_unique_id_is_scoped_by_gateway(patched_hass, mock_api):
    """Returns a gateway-scoped ID for a child device."""
    subject = TuyaLocalDevice(
        "Some name",
        "gateway_id",
        "some.ip.address",
        "some_local_key",
        "3.3",
        "child_id",
        patched_hass,
    )

    assert subject.unique_id == "gateway_id/child_id"


def test_device_info(subject, mock_api):
    """Returns generic info plus the unique ID for categorisation."""
    assert subject.device_info == {
        "identifiers": {("tuya_local", mock_api().id)},
        "name": "Some name",
        "manufacturer": "Tuya",
    }


@pytest.mark.asyncio
async def test_delete_keeps_device_entry_when_stop_fails(hass, mocker):
    """Device cache should not be removed before stop succeeds."""
    device = mocker.MagicMock()
    device.async_stop = mocker.AsyncMock(side_effect=RuntimeError("stop failed"))
    hass.data[DOMAIN] = {
        "deviceid": {
            "device": device,
            "tuyadevice": mocker.MagicMock(),
            "tuyadevicelock": mocker.MagicMock(),
        }
    }

    with pytest.raises(RuntimeError, match="stop failed"):
        await async_delete_device(hass, {CONF_DEVICE_ID: "deviceid"})

    assert hass.data[DOMAIN]["deviceid"]["device"] is device


def test_has_returned_state(subject):
    """Returns True if the device has returned its state."""
    subject._cached_state = EUROM_600_HEATER_PAYLOAD
    assert subject.has_returned_state

    subject._cached_state = {"updated_at": 0}
    assert not subject.has_returned_state


@pytest.mark.asyncio
async def test_refreshes_state_if_no_cached_state_exists(subject, mocker):
    subject._cached_state = {}
    subject.async_refresh = mocker.AsyncMock()

    await subject.async_inferred_type()

    subject.async_refresh.assert_awaited()


@pytest.mark.asyncio
async def test_detection_returns_none_when_device_type_not_detected(subject):
    subject._cached_state = {"192": False, "updated_at": time()}
    assert await subject.async_inferred_type() is None


@pytest.mark.asyncio
async def test_refresh_retries_up_to_eleven_times(subject, mock_api):
    subject._api_protocol_working = False
    mock_api().status.side_effect = [
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        {"dps": {"1": False}},
    ]

    await subject.async_refresh()

    assert mock_api().status.call_count == 11
    assert subject._cached_state["1"] is False


@pytest.mark.asyncio
async def test_refresh_clears_cache_after_allowed_failures(subject, mock_api):
    subject._cached_state = {"1": True}
    subject._pending_updates = {
        "1": {"value": False, "updated_at": time(), "sent": True}
    }
    mock_api().status.side_effect = [
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
    ]

    await subject.async_refresh()

    assert mock_api().status.call_count == 3
    assert subject._cached_state == {"updated_at": 0}
    assert subject._pending_updates == {}


@pytest.mark.asyncio
async def test_api_protocol_version_is_rotated_with_each_failure(
    subject, mock_api, mocker
):
    subject._api_protocol_version_index = None
    subject._api_protocol_working = False
    mock_api().status.side_effect = [
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
    ]
    await subject.async_refresh()

    mock_api().set_version.assert_has_calls(
        [
            mocker.call(3.3),
            mocker.call(3.1),
            mocker.call(3.2),
            mocker.call(3.4),
            mocker.call(3.5),
            mocker.call(3.3),
            mocker.call(3.4),
            mocker.call(3.5),
            mocker.call(3.3),
            mocker.call(3.1),
            mocker.call(3.2),
            mocker.call(3.4),
            mocker.call(3.5),
            mocker.call(3.3),
            mocker.call(3.4),
            mocker.call(3.5),
            mocker.call(3.3),
            mocker.call(3.1),
        ]
    )


@pytest.mark.asyncio
async def test_api_protocol_version_is_stable_once_successful(
    subject, mock_api, mocker
):
    subject._api_protocol_version_index = None
    subject._api_protocol_working = False
    mock_api().status.side_effect = [
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        {"dps": {"1": False}},
        {"dps": {"1": False}},
        Exception("Error"),
        Exception("Error"),
        {"dps": {"1": False}},
    ]

    await subject.async_refresh()
    assert subject._api_protocol_version_index == 3
    assert subject._api_protocol_working
    await subject.async_refresh()
    assert subject._api_protocol_version_index == 3
    await subject.async_refresh()
    assert subject._api_protocol_version_index == 3

    mock_api().set_version.assert_has_calls(
        [
            mocker.call(3.1),
            mocker.call(3.2),
            mocker.call(3.4),
        ]
    )


@pytest.mark.asyncio
async def test_api_protocol_version_is_not_rotated_when_not_auto(subject, mock_api):
    # Set up preconditions for the test

    subject._protocol_configured = 3.4
    subject._api_protocol_version_index = None
    subject._api_protocol_working = False
    mock_api().status.side_effect = [
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        {"dps": {"1": False}},
        {"dps": {"1": False}},
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        Exception("Error"),
        {"dps": {"1": False}},
    ]
    await subject._rotate_api_protocol_version()
    mock_api().set_version.assert_called_once_with(3.4)
    mock_api().set_version.reset_mock()

    await subject.async_refresh()
    assert subject._api_protocol_version_index == 3
    await subject.async_refresh()
    assert subject._api_protocol_version_index == 3
    await subject.async_refresh()
    assert subject._api_protocol_version_index == 3


def test_reset_cached_state_clears_cached_state_and_pending_updates(subject):
    subject._cached_state = {"1": True, "updated_at": time()}
    subject._pending_updates = {
        "1": {"value": False, "updated_at": time(), "sent": True}
    }

    subject._reset_cached_state()

    assert subject._cached_state == {"updated_at": 0}
    assert subject._pending_updates == {}


def test_get_property_returns_value_from_cached_state(subject):
    subject._cached_state = {"1": True}
    assert subject.get_property("1") is True


def test_get_property_returns_pending_update_value(subject):
    subject._pending_updates = {
        "1": {"value": False, "updated_at": time() - 4, "sent": True}
    }
    assert subject.get_property("1") is False


def test_pending_update_value_overrides_cached_value(subject):
    subject._cached_state = {"1": True}
    subject._pending_updates = {
        "1": {"value": False, "updated_at": time() - 4, "sent": True}
    }

    assert subject.get_property("1") is False


def test_expired_pending_update_value_does_not_override_cached_value(subject):
    subject._cached_state = {"1": True}
    subject._pending_updates = {
        "1": {"value": False, "updated_at": time() - 5, "sent": True}
    }

    assert subject.get_property("1") is True


def test_get_property_returns_none_when_value_does_not_exist(subject):
    subject._cached_state = {"1": True}
    assert subject.get_property("2") is None


@pytest.mark.asyncio
async def test_async_set_property_sends_to_api(subject, mock_api):
    await subject.async_set_property("1", False)

    mock_api().set_multiple_values.assert_called_once()


@pytest.mark.asyncio
async def test_set_property_immediately_stores_pending_updates(subject):
    subject._cached_state = {"1": True}
    await subject.async_set_property("1", False)
    assert not subject.get_property("1")


@pytest.mark.asyncio
async def test_set_properties_takes_no_action_when_nothing_provided(subject, mocker):
    mock = mocker.patch("asyncio.sleep")
    await subject.async_set_properties({})
    mock.assert_not_called()


def test_anticipate_property_value_updates_cached_state(subject):
    subject._cached_state = {"1": True}
    subject.anticipate_property_value("1", False)
    assert subject._cached_state["1"] is False


def test_get_key_for_value_returns_key_from_object_matching_value(subject):
    obj = {"key1": "value1", "key2": "value2"}

    assert TuyaLocalDevice.get_key_for_value(obj, "value1") == "key1"
    assert TuyaLocalDevice.get_key_for_value(obj, "value2") == "key2"


def test_get_key_for_value_returns_fallback_when_value_not_found(subject):
    obj = {"key1": "value1", "key2": "value2"}
    assert TuyaLocalDevice.get_key_for_value(obj, "value3", fallback="fb") == "fb"


def test_refresh_cached_state(subject, mock_api):
    # set up preconditions
    mock_api().status.return_value = {"dps": {"1": "CHANGED"}}
    subject._cached_state = {"1": "UNCHANGED", "updated_at": 123}

    # call the function under test
    subject._refresh_cached_state()

    # Did it call the API as expected?
    mock_api().status.assert_called_once()
    # Did it update the cached state?
    assert subject._cached_state == {"1": "CHANGED"} | subject._cached_state
    # Did it update the timestamp on the cached state?
    assert subject._cached_state["updated_at"] == pytest.approx(time(), abs=2)


@pytest.mark.asyncio
async def test_set_values(subject, mock_api):
    # set up preconditions
    subject._pending_updates = {
        "1": {"value": "sample", "updated_at": time() - 2, "sent": False},
    }

    # call the function under test
    await subject._send_pending_updates()

    # did it send what it was asked?
    mock_api().set_multiple_values.assert_called_once_with({"1": "sample"}, nowait=True)
    # did it mark the pending updates as sent?
    assert subject._pending_updates["1"]["sent"]
    # did it update the time on the pending updates?
    assert subject._pending_updates["1"]["updated_at"] == pytest.approx(time(), abs=2)
    # did it lock and unlock when sending
    # subject._lock.acquire.assert_called_once()
    # subject._lock.release.assert_called_once()


def test_pending_updates_cleared_on_receipt(subject):
    # Set up the preconditions
    now = time()
    subject._pending_updates = {
        "1": {"value": True, "updated_at": now, "sent": True},
        "2": {"value": True, "updated_at": now, "sent": False},  # unsent
        "3": {"value": True, "updated_at": now, "sent": True},  # unmatched
        "4": {"value": True, "updated_at": now, "sent": True},  # not received
    }
    subject._remove_properties_from_pending_updates({"1": True, "2": True, "3": False})
    assert subject._pending_updates == {
        "2": {"value": True, "updated_at": now, "sent": False},
        "3": {"value": True, "updated_at": now, "sent": True},
        "4": {"value": True, "updated_at": now, "sent": True},
    }


def test_actually_start(subject, mocker, patched_hass):
    # Set up the preconditions
    mocker.patch.object(subject, "receive_loop", return_value="LOOP")
    mocker.patch.object(subject, "_refresh_task", new=mocker.AsyncMock)
    subject._running = False
    mocker.patch.object(patched_hass, "async_create_task")
    # patched_hass.async_create_task = mocker.MagicMock()
    # patched_hass.bus.async_listen_once = mocker.AsyncMock()
    # patched_hass.bus.async_listen_once.return_value = "LISTENER"
    # run the function under test
    subject.actually_start()

    # did it register a listener for EVENT_HOMEASSISTANT_STOP?
    # patched_hass.bus.async_listen_once.assert_called_once_with(
    #     EVENT_HOMEASSISTANT_STOP, subject.async_stop
    # )
    # assert subject._shutdown_listener == "LISTENER"
    # did it set the running flag?
    assert subject._running
    # did it schedule the loop?
    # task.assert_called_once()


def test_start_starts_when_ha_running(subject, patched_hass, mocker):
    # Set up preconditions
    patched_hass.is_running = True
    listener = mocker.MagicMock()
    subject._startup_listener = listener
    subject.actually_start = mocker.MagicMock()

    # Call the function under test
    subject.start()

    # Did it actually start?
    subject.actually_start.assert_called_once()
    # Did it cancel the startup listener?
    assert subject._startup_listener is None
    listener.assert_called_once()


def test_start_schedules_for_later_when_ha_starting(subject, patched_hass, mocker):
    # Set up preconditions
    patched_hass.is_running = False
    subject.actually_start = mocker.MagicMock()

    # Call the function under test
    subject.start()

    # Did it avoid actually starting?
    subject.actually_start.assert_not_called()
    # Did it register a listener?
    # assert subject._startup_listener == "LISTENER"
    # patched_hass.bus.async_listen_once.assert_called_once_with(
    #     EVENT_HOMEASSISTANT_STARTED, subject.actually_start
    # )


def test_start_does_nothing_when_ha_stopping(subject, patched_hass, mocker):
    # Set up preconditions
    patched_hass.is_running = True
    patched_hass.is_stopping = True
    subject.actually_start = mocker.MagicMock()

    # Call the function under test
    subject.start()

    # Did it avoid actually starting?
    subject.actually_start.assert_not_called()
    # Did it avoid registering a listener?
    # patched_hass.bus.async_listen_once.assert_not_called()
    assert subject._startup_listener is None


@pytest.mark.asyncio
async def test_async_stop(subject, mocker):
    # Set up preconditions
    listener = mocker.MagicMock()
    subject._refresh_task = None
    subject._shutdown_listener = listener
    subject._children = [1, 2, 3]

    # Call the function under test
    await subject.async_stop()

    # Shutdown listener doesn't get cancelled as HA does that
    listener.assert_not_called()
    # Were the child entities cleared?
    assert subject._children == []
    # Did it wait for the refresh task to finish then clear it?
    # This doesn't work because AsyncMock only mocks awaitable method calls
    # but we want an awaitable object
    # refresh.assert_awaited_once()
    assert subject._refresh_task is None


@pytest.mark.asyncio
async def test_async_stop_when_not_running(subject):
    # Set up preconditions
    _refresh_task = None
    subject._shutdown_listener = None
    subject._children = []

    # Call the function under test
    await subject.async_stop()

    # Was the shutdown listener left empty?
    assert subject._shutdown_listener is None
    # Were the child entities cleared?
    assert subject._children == []
    # Was the refresh task left empty?
    assert subject._refresh_task is None


def test_register_first_entity_ha_running(subject, mocker):
    # Set up preconditions
    subject._children = []
    subject._running = False
    subject._startup_listener = None
    subject.start = mocker.MagicMock()
    entity = mocker.AsyncMock()
    entity._config = mocker.MagicMock()
    entity._config.dps.return_value = []
    # despite the name, the below HA function is not async and does not need to be awaited
    entity.async_schedule_update_ha_state = mocker.MagicMock()

    # Call the function under test
    subject.register_entity(entity)

    # Was the entity added to the list?
    assert subject._children == [entity]

    # Did we start the loop?
    subject.start.assert_called_once()


def test_register_subsequent_entity_ha_running(subject, mocker):
    # Set up preconditions
    first = mocker.AsyncMock()
    second = mocker.AsyncMock()
    second._config = mocker.MagicMock()
    second._config.dps.return_value = []
    subject._children = [first]
    subject._running = True

    subject._startup_listener = None
    subject.start = mocker.MagicMock()

    # Call the function under test
    subject.register_entity(second)

    # Was the entity added to the list?
    assert set(subject._children) == set([first, second])

    # Did we avoid restarting the loop?
    subject.start.assert_not_called()


def test_register_subsequent_entity_ha_starting(subject, mocker):
    # Set up preconditions
    first = mocker.AsyncMock()
    second = mocker.AsyncMock()
    second._config = mocker.MagicMock()
    second._config.dps.return_value = []
    subject._children = [first]
    subject._running = False
    subject._startup_listener = mocker.MagicMock()
    subject.start = mocker.MagicMock()

    # Call the function under test
    subject.register_entity(second)

    # Was the entity added to the list?
    assert set(subject._children) == set([first, second])
    # Did we avoid restarting the loop?
    subject.start.assert_not_called()


@pytest.mark.asyncio
async def test_unregister_one_of_many_entities(subject, mocker):
    # Set up preconditions
    subject._children = ["First", "Second"]
    subject.async_stop = mocker.AsyncMock()

    # Call the function under test
    await subject.async_unregister_entity("First")

    # Was the entity removed from the list?
    assert set(subject._children) == set(["Second"])
    # Is the loop still running?
    subject.async_stop.assert_not_called()


@pytest.mark.asyncio
async def test_unregister_last_entity(subject, mocker):
    # Set up preconditions
    subject._children = ["Last"]
    subject.async_stop = mocker.AsyncMock()

    # Call the function under test
    await subject.async_unregister_entity("Last")

    # Was the entity removed from the list?
    assert subject._children == []
    # Was the loop stopped?
    subject.async_stop.assert_called_once()


@pytest.mark.asyncio
async def test_async_receive(subject, mock_api, mocker):
    # Set up preconditions
    mock_api().status.return_value = {"dps": {"1": "INIT", "2": 2}}
    mock_api().receive.return_value = {"1": "UPDATED"}
    subject._running = True
    subject._cached_state = {"updated_at": 0}
    # Call the function under test
    print("starting test loop...")
    loop = subject.async_receive()
    print("getting first iteration...")
    result = await loop.__anext__()

    # Check that the loop was started, but without persistent connection
    # since there was no state returned yet and it might need to negotiate
    # version.
    mock_api().set_socketPersistent.assert_called_once_with(False)
    # Check that a full poll was done
    mock_api().status.assert_called_once()
    assert result == {"1": "INIT", "2": 2, "full_poll": True}
    # Prepare for next round
    subject._cached_state = subject._cached_state | result
    mock_api().status.reset_mock()
    mock_api().set_socketPersistent.reset_mock()
    print("getting second iteration...")
    result = await loop.__anext__()
    # Check that the connection was made persistent now that data has been
    # returned
    mock_api().set_socketPersistent.assert_called_once_with(True)
    mock_api().status.reset_mock()
    # Wait long enough to force a heartbeat poll on the next iteration
    subject._cached_state = subject._cached_state | {"updated_at": time()}
    await asyncio.sleep(10.1)
    print("getting third iteration...")
    # Call the function under test
    result = await loop.__anext__()

    # Check that a heartbeat poll was done
    mock_api().status.assert_not_called()
    mock_api().heartbeat.assert_called_once()
    mock_api().receive.assert_called_once()
    assert result == {"1": "UPDATED", "full_poll": False}
    # Prepare for next iteration
    subject._running = False
    mock_api().set_socketPersistent.reset_mock()

    # Call the function under test
    print("getting last iteration...")
    try:
        result = await loop.__anext__()
        pytest.fail("Should have raised an exception to quit the loop")
    # Check that the loop terminated
    except StopAsyncIteration:
        pass
    mock_api().set_socketPersistent.assert_called_once_with(False)


def test_should_poll(subject):
    subject._cached_state = {"1": "sample", "updated_at": time()}
    subject._poll_only = False
    subject._temporary_poll = False

    # Test temporary poll via pause/resume
    assert not subject.should_poll
    subject.pause()
    assert subject.should_poll
    subject.resume()
    assert not subject.should_poll

    # Test configured polling
    subject._poll_only = True
    assert subject.should_poll
    subject._poll_only = False

    # Test initial polling
    subject._cached_state = {}
    assert subject.should_poll


@pytest.mark.asyncio
async def test_refresh_error_reports_device_error_code(subject, mock_api, caplog):
    """The error code and message returned by the device are logged."""
    subject._api_protocol_working = False
    subject._protocol_configured = "3.3"
    mock_api().status.return_value = {
        "Error": "Check device key or version",
        "Err": "914",
        "Payload": None,
    }

    with caplog.at_level(logging.ERROR):
        await subject.async_refresh()

    assert "914" in caplog.text
    assert "Check device key or version" in caplog.text
    # 914 is ambiguous, so the possible causes are spelled out
    assert "power cycled" in caplog.text


@pytest.mark.asyncio
async def test_refresh_error_without_error_code_is_unchanged(subject, mock_api, caplog):
    """A failure that is not a device error logs the bare message."""
    subject._api_protocol_working = False
    subject._protocol_configured = "3.3"
    mock_api().status.side_effect = Exception("connection refused")

    with caplog.at_level(logging.ERROR):
        await subject.async_refresh()

    assert "Failed to refresh device state for Some name." in caplog.text
    assert "Device reported error" not in caplog.text


@pytest.mark.asyncio
async def test_refresh_error_914_stays_quiet_when_rotating_protocols(
    subject, mock_api, caplog
):
    """914 is expected while auto-detecting, so it must not log at error."""
    subject._api_protocol_working = False
    subject._protocol_configured = "auto"
    mock_api().status.return_value = {
        "Error": "Check device key or version",
        "Err": "914",
        "Payload": None,
    }

    with caplog.at_level(logging.ERROR):
        await subject.async_refresh()

    assert caplog.text == ""


def test_explicit_refresh_query_uses_helper(subject, mocker):
    helper = mocker.patch(
        "custom_components.tuya_local.device.query_refreshed_dps",
        return_value={"dps": {"20": True}},
    )
    subject._refresh_dps = [20, 21]
    assert subject._query_state() == {"dps": {"20": True}}
    helper.assert_called_once_with(subject._api, [20, 21])
    subject._api.status.assert_not_called()


def test_default_query_preserves_status(subject):
    subject._api.status.return_value = {"dps": {"1": True}}
    assert subject._query_state() == {"dps": {"1": True}}
    subject._api.status.assert_called_once_with()


def test_explicit_refresh_rejects_gateway_child(patched_hass):
    with pytest.raises(ValueError, match="direct devices only"):
        TuyaLocalDevice(
            "Test child",
            "gateway",
            "test.invalid",
            "test-key",
            "3.5",
            "child-id",
            patched_hass,
            refresh_dpids="20,21",
        )


@pytest.mark.parametrize(
    "refresh_value,expected", [("20,21,24", [20, 21, 24]), ("", [])]
)
def test_setup_device_keeps_refresh_setting(
    patched_hass, mock_api, refresh_value, expected
):
    from custom_components.tuya_local.device import setup_device

    device = setup_device(
        patched_hass,
        {
            "name": "Test light",
            "device_id": "test-device",
            "host": "test.invalid",
            "local_key": "test-only-key",
            "protocol_version": 3.5,
            "poll_only": False,
            "refresh_dpids": refresh_value,
        },
    )
    assert device._refresh_dps == expected
    assert patched_hass.data[DOMAIN]["test-device"]["device"] is device


@pytest.mark.asyncio
async def test_sender_handles_removed_pending_entry(subject, mock_api):
    subject._add_properties_to_pending_updates({"24": "red"})

    def send(properties, nowait):
        subject._pending_updates.clear()

    mock_api().set_multiple_values.side_effect = send
    await subject._send_pending_updates()
    mock_api().set_multiple_values.assert_called_once_with({"24": "red"}, nowait=True)
    assert subject._pending_updates == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement", ["red", "blue"])
async def test_sender_does_not_mark_new_request_sent(subject, mock_api, replacement):
    subject._add_properties_to_pending_updates({"24": "red"})

    def send(properties, nowait):
        subject._add_properties_to_pending_updates({"24": replacement})

    mock_api().set_multiple_values.side_effect = send
    await subject._send_pending_updates()
    assert subject._pending_updates["24"]["value"] == replacement
    assert subject._pending_updates["24"]["sent"] is False


@pytest.mark.asyncio
async def test_queued_senders_send_latest_once(subject, mock_api):
    mock_api().set_multiple_values.return_value = None
    subject._add_properties_to_pending_updates({"24": "red"})
    await subject._api_lock.acquire()
    first = asyncio.create_task(subject._send_pending_updates())
    second = asyncio.create_task(subject._send_pending_updates())
    await asyncio.sleep(0)
    subject._add_properties_to_pending_updates({"24": "blue"})
    subject._api_lock.release()
    await asyncio.gather(first, second)
    mock_api().set_multiple_values.assert_called_once_with({"24": "blue"}, nowait=True)
    assert subject._pending_updates["24"]["sent"] is True


@pytest.mark.asyncio
async def test_send_error_retries_without_marking_sent(subject, mock_api):
    subject._add_properties_to_pending_updates({"24": "red"})
    observations = []

    def send(properties, nowait):
        observations.append(subject._pending_updates["24"]["sent"])
        if len(observations) == 1:
            return {"Err": "914", "Error": "session negotiation failed"}
        return None

    mock_api().set_multiple_values.side_effect = send
    await subject._send_pending_updates()
    assert observations == [False, False]
    assert subject._pending_updates["24"]["sent"] is True


@pytest.mark.asyncio
async def test_empty_pending_does_not_send(subject, mock_api):
    await subject._send_pending_updates()
    mock_api().set_multiple_values.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [KeyError("24"), TypeError("test"), IndexError("test")]
)
async def test_programming_error_does_not_reset_socket(subject, mocker, error):
    call = mocker.Mock(side_effect=error)
    with pytest.raises(type(error)):
        await subject._retry_on_failed_connection(call, "Test operation")
    call.assert_called_once_with()
    subject._api.set_socketPersistent.assert_not_called()


@pytest.mark.asyncio
async def test_real_worker_preserves_command_added_during_send(
    subject, mock_api, mocker
):
    """Use barriers and a real worker instead of synchronous executor mocks."""
    import threading

    loop = asyncio.get_running_loop()
    main_thread = threading.get_ident()
    started = asyncio.Event()
    release = threading.Event()
    bookkeeping_threads = []
    original_get = subject._get_pending_updates

    def get_pending():
        bookkeeping_threads.append(threading.get_ident())
        return original_get()

    mocker.patch.object(subject, "_get_pending_updates", side_effect=get_pending)

    def send(properties, nowait):
        assert threading.get_ident() != main_thread
        loop.call_soon_threadsafe(started.set)
        if not release.wait(3):
            raise RuntimeError("Test barrier timed out")
        return None

    async def executor(func, *args):
        return await asyncio.to_thread(func, *args)

    mocker.patch.object(subject._hass, "async_add_executor_job", side_effect=executor)
    mock_api().set_multiple_values.side_effect = send
    subject._add_properties_to_pending_updates({"24": "red"})
    task = asyncio.create_task(subject._send_pending_updates())
    try:
        await asyncio.wait_for(started.wait(), 3)
        subject._add_properties_to_pending_updates({"24": "blue"})
    finally:
        release.set()
        await task
    assert subject._pending_updates["24"]["value"] == "blue"
    assert subject._pending_updates["24"]["sent"] is False
    assert set(bookkeeping_threads) == {main_thread}


@pytest.mark.asyncio
async def test_retry_rebuilds_request_when_new_command_arrives(subject, mock_api):
    subject._add_properties_to_pending_updates({"24": "red"})
    requests = []

    def send(properties, nowait):
        requests.append(properties.copy())
        if len(requests) == 1:
            subject._add_properties_to_pending_updates({"24": "blue"})
            return {"Error": "connection failed", "Err": "901"}
        return None

    mock_api().set_multiple_values.side_effect = send
    await subject._send_pending_updates()
    assert requests == [{"24": "red"}, {"24": "blue"}]
    assert subject._pending_updates["24"]["sent"] is True


@pytest.mark.asyncio
async def test_control_error_900_is_not_status_success(subject, mock_api):
    subject._add_properties_to_pending_updates({"24": "red"})
    observations = []

    def send(properties, nowait):
        observations.append(subject._pending_updates["24"]["sent"])
        return {"Error": "invalid command", "Err": "900"}

    mock_api().set_multiple_values.side_effect = send
    await subject._send_pending_updates()
    assert observations == [False, False, False]
    assert subject._pending_updates == {}
    assert subject._api_working_protocol_failures == 1


@pytest.mark.asyncio
async def test_cancelled_queued_sender_does_not_send_or_mark(subject, mock_api):
    subject._add_properties_to_pending_updates({"24": "red"})
    await subject._api_lock.acquire()
    task = asyncio.create_task(subject._send_pending_updates())
    await asyncio.sleep(0)
    task.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        subject._api_lock.release()
    mock_api().set_multiple_values.assert_not_called()
    assert subject._pending_updates["24"]["sent"] is False


@pytest.mark.asyncio
async def test_runtime_refresh_ignores_ack_and_merges_reports(
    subject, mock_api, mocker
):
    subject._refresh_dps = [20, 21]
    subject._cached_state = {"20": False, "21": "white", "updated_at": time()}
    subject._last_full_poll = 0
    subject._running = True
    mock_api().parent = None
    mock_api().updatedps.return_value = None
    blocking_query = mocker.patch.object(subject, "_query_state")
    receive = mocker.patch(
        "custom_components.tuya_local.device.receive_available_dps",
        side_effect=[None, {"dps": {"20": True}}, {"dps": {"21": "colour"}}],
    )
    mocker.patch("custom_components.tuya_local.device.asyncio.sleep")
    loop = subject.async_receive()
    try:
        first = await asyncio.wait_for(loop.__anext__(), 2)
        second = await asyncio.wait_for(loop.__anext__(), 2)
        assert first == {"20": True, "full_poll": False}
        assert second == {"20": True, "21": "colour", "full_poll": True}
        mock_api().updatedps.assert_called_once_with([20, 21], nowait=True)
        blocking_query.assert_not_called()
        assert receive.call_count == 3
        assert subject._api_working_protocol_failures == 0
        assert all(
            c.args != (False,) for c in mock_api().set_socketPersistent.call_args_list
        )
    finally:
        subject._running = False
        with pytest.raises(StopAsyncIteration):
            await loop.__anext__()


@pytest.mark.asyncio
async def test_missing_runtime_report_does_not_flood_or_disconnect(
    subject, mock_api, mocker
):
    subject._refresh_dps = [20]
    subject._cached_state = {"20": True, "updated_at": time() - 100}
    subject._running = True
    subject._last_full_poll = 0
    mock_api().parent = None
    mock_api().updatedps.return_value = None
    mocker.patch.object(subject, "_query_state")
    reads = []

    def no_report(api):
        reads.append(True)
        if len(reads) == 5:
            subject._running = False
        return None

    mocker.patch(
        "custom_components.tuya_local.device.receive_available_dps",
        side_effect=no_report,
    )
    mocker.patch("custom_components.tuya_local.device.asyncio.sleep")
    loop = subject.async_receive()
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(loop.__anext__(), 2)
    assert len(reads) == 5
    mock_api().updatedps.assert_called_once_with([20], nowait=True)
    # Only the final shutdown may disable persistence.
    assert [c.args for c in mock_api().set_socketPersistent.call_args_list].count(
        (False,)
    ) == 1
    assert subject._api_working_protocol_failures == 0


@pytest.mark.asyncio
async def test_explicit_startup_keeps_bounded_collector(subject, mock_api, mocker):
    subject._refresh_dps = [20]
    subject._cached_state = {"updated_at": 0}
    subject._running = True
    mock_api().parent = None
    query = mocker.patch.object(
        subject, "_query_state", return_value={"dps": {"20": True}}
    )
    loop = subject.async_receive()
    assert await loop.__anext__() == {"20": True, "full_poll": True}
    query.assert_called_once()
    mock_api().updatedps.assert_not_called()
    subject._running = False
    with pytest.raises(StopAsyncIteration):
        await loop.__anext__()


@pytest.mark.asyncio
async def test_explicit_heartbeat_and_receive_wait_for_api_lock(
    subject, mock_api, mocker
):
    subject._refresh_dps = [20]
    subject._cached_state = {"20": True, "updated_at": time() - 10}
    subject._last_full_poll = time()
    subject._running = True
    mock_api().parent = None
    mock_api().heartbeat.return_value = None
    events = []
    mock_api().heartbeat.side_effect = lambda *_: events.append("heartbeat")

    def receive(api):
        events.append("receive")
        assert subject._api_lock.locked()
        return {"dps": {"20": True}}

    mocker.patch(
        "custom_components.tuya_local.device.receive_available_dps", side_effect=receive
    )
    await subject._api_lock.acquire()
    loop = subject.async_receive()
    task = asyncio.create_task(loop.__anext__())
    try:
        await asyncio.sleep(0)
        assert events == []
    finally:
        subject._api_lock.release()
    assert await task == {"20": True, "full_poll": False}
    assert events == ["heartbeat", "receive"]
    subject._running = False
    with pytest.raises(StopAsyncIteration):
        await loop.__anext__()


def test_runtime_partial_reports_do_not_clear_other_state(subject):
    subject._refresh_dps = [20, 21]
    subject._runtime_refresh_data = {}
    first, full = subject._merge_runtime_refresh({"dps": {"20": True}})
    assert first == {"dps": {"20": True}}
    assert full is False
    second, full = subject._merge_runtime_refresh({"data": {"dps": {"21": "white"}}})
    assert second == {"dps": {"20": True, "21": "white"}}
    assert full is True
    assert subject._runtime_refresh_data is None
    assert subject._merge_runtime_refresh({"dps": {"24": "red"}}) == (
        {"dps": {"24": "red"}},
        False,
    )


@pytest.mark.asyncio
async def test_actual_receive_error_still_disables_connection(
    subject, mock_api, mocker
):
    subject._refresh_dps = [20]
    subject._cached_state = {"20": True, "updated_at": time()}
    subject._last_full_poll = time()
    subject._running = True
    mock_api().parent = None

    def receive(api):
        subject._running = False
        return {"Error": "connection lost", "Err": "901"}

    mocker.patch(
        "custom_components.tuya_local.device.receive_available_dps", side_effect=receive
    )
    mocker.patch("custom_components.tuya_local.device.asyncio.sleep")
    loop = subject.async_receive()
    with pytest.raises(StopAsyncIteration):
        await loop.__anext__()
    mock_api().set_socketPersistent.assert_any_call(False)
    assert subject._api_working_protocol_failures == 1


@pytest.mark.asyncio
async def test_real_runtime_refresh_allows_control_between_ack_and_reports(
    subject, mocker
):
    """Real TinyTuya 3.5 plus a socketpair reproduces the delayed-report path."""
    import json
    import socket

    from tinytuya.core.Device import Device
    from tinytuya.core.message_helper import TuyaMessage, pack_message

    from custom_components.tuya_local.helpers.dps_refresh import receive_available_dps

    key = b"0123456789abcdef"
    reader, server = socket.socketpair()
    server.setblocking(False)
    api = Device("test-device", "127.0.0.1", key.decode())
    api.set_version(3.5)
    api.set_socketPersistent(True)
    api.socket = reader
    subject._api = api
    subject._refresh_dps = [20, 21]
    subject._cached_state = {"20": False, "updated_at": time()}
    subject._last_full_poll = 0
    subject._running = True
    loop = asyncio.get_running_loop()
    ack_seen = asyncio.Event()
    commands = []

    async def executor(func, *args):
        return await asyncio.to_thread(func, *args)

    def receive(api):
        result = receive_available_dps(api)
        if result is None and any(msg.cmd == 13 for msg in api.raw_recv):
            loop.call_soon_threadsafe(ack_seen.set)
        return result

    mocker.patch.object(subject._hass, "async_add_executor_job", side_effect=executor)
    mocker.patch(
        "custom_components.tuya_local.device.receive_available_dps", side_effect=receive
    )

    async def read_frame():
        data = b""
        while len(data) < 18:
            data += await loop.sock_recv(server, 18 - len(data))
        length = int.from_bytes(data[14:18], "big") + 4
        while len(data) < 18 + length:
            data += await loop.sock_recv(server, 18 + length - len(data))
        return int.from_bytes(data[10:14], "big")

    async def send_frame(seq, cmd, payload):
        message = TuyaMessage(seq, cmd, 0, payload, 0, True, 0x6699, b"0123456789ab")
        await loop.sock_sendall(server, pack_message(message, hmac_key=key))

    async def device_server():
        commands.append(await read_frame())
        await send_frame(1, 13, b"")
        await asyncio.wait_for(ack_seen.wait(), 2)
        # Hold the state report until a CONTROL has passed through the same
        # API lock; a blocking collector would prevent this from completing.
        commands.append(await read_frame())
        await send_frame(2, 8, json.dumps({"dps": {"20": True}}).encode())
        await send_frame(3, 8, json.dumps({"dps": {"21": "colour"}}).encode())

    receiver = subject.async_receive()
    next_report = asyncio.create_task(receiver.__anext__())
    server_task = asyncio.create_task(device_server())
    try:
        await asyncio.wait_for(ack_seen.wait(), 2)
        assert api.socket is reader
        await asyncio.wait_for(subject.async_set_properties({"24": "red"}), 1)
        first = await asyncio.wait_for(next_report, 2)
        second = await asyncio.wait_for(receiver.__anext__(), 2)
        await asyncio.wait_for(server_task, 2)
        assert commands == [18, 13]
        assert first == {"20": True, "full_poll": False}
        assert second == {"20": True, "21": "colour", "full_poll": True}
        assert api.socket is reader
        assert subject._api_working_protocol_failures == 0
    finally:
        subject._running = False
        for task in [next_report, server_task]:
            if not task.done():
                task.cancel()
        await asyncio.gather(next_report, server_task, return_exceptions=True)
        await receiver.aclose()
        reader.close()
        server.close()
        api.socket = None


@pytest.mark.asyncio
async def test_incomplete_runtime_refresh_reissues_only_after_interval(
    subject, mock_api, mocker
):
    subject._refresh_dps = [20]
    subject._cached_state = {"20": True, "updated_at": time() - 100}
    subject._last_full_poll = 0
    subject._running = True
    mock_api().parent = None
    mock_api().updatedps.return_value = None
    clock = [time()]
    mocker.patch(
        "custom_components.tuya_local.device.time", side_effect=lambda: clock[0]
    )
    reads = []

    def receive(api):
        reads.append(True)
        if len(reads) == 1:
            clock[0] += subject._POLLING_INTERVAL + 1
        else:
            subject._running = False
        return None

    mocker.patch(
        "custom_components.tuya_local.device.receive_available_dps", side_effect=receive
    )
    mocker.patch("custom_components.tuya_local.device.asyncio.sleep")
    with pytest.raises(StopAsyncIteration):
        await subject.async_receive().__anext__()
    assert mock_api().updatedps.call_count == 2
    assert len(reads) == 2
    assert subject._api_working_protocol_failures == 0


@pytest.mark.asyncio
async def test_explicit_poll_only_keeps_original_collector(subject, mock_api, mocker):
    subject._refresh_dps = [20]
    subject._poll_only = True
    subject._cached_state = {"20": True, "updated_at": time() - 100}
    subject._running = True
    mock_api().parent = None
    query = mocker.patch.object(
        subject, "_query_state", return_value={"dps": {"20": True}}
    )
    receive = mocker.patch("custom_components.tuya_local.device.receive_available_dps")
    gen = subject.async_receive()
    assert await gen.__anext__() == {"20": True, "full_poll": True}
    query.assert_called_once()
    receive.assert_not_called()
    subject._running = False
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
