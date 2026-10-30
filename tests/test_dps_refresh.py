"""Characterize the working installed helper without changing its receive policy."""

from unittest.mock import Mock, patch

import pytest

from custom_components.tuya_local.helpers.dps_refresh import (
    parse_refresh_dpids,
    query_refreshed_dps,
    validate_refresh_dpids,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", []), ("  ", []), ("20,21,24,20", [20, 21, 24]), ("1,255", [1, 255])],
)
def test_parse_refresh_ids(value, expected):
    assert parse_refresh_dpids(value) == expected
    assert validate_refresh_dpids(value) == value


@pytest.mark.parametrize(
    "value", [None, [], "0", "256", "20,,21", "-1", "２０", ",".join(["1"] * 33)]
)
def test_invalid_refresh_ids(value):
    with pytest.raises(ValueError):
        parse_refresh_dpids(value)


@pytest.fixture
def api():
    api = Mock(socketPersistent=True, connection_timeout=5, retry=True)
    api.updatedps.return_value = None
    return api


def assert_restored(api):
    api.set_socketPersistent.assert_any_call(True)
    assert api.set_socketPersistent.call_args.args == (True,)
    assert api.set_socketTimeout.call_args.args == (5,)
    assert api.set_retry.call_args.args == (True,)


def test_split_reports_merge(api):
    api.receive.side_effect = [
        {"dps": {"20": True}},
        {"data": {"dps": {"21": "white"}}},
        None,
    ]
    assert query_refreshed_dps(api, [20, 21]) == {"dps": {"20": True, "21": "white"}}
    api.updatedps.assert_called_once_with([20, 21], nowait=True)
    assert_restored(api)


def test_baseline_empty_ack_still_returns_902(api):
    """Record the known limitation; the baseline is NOT the proposed fix."""
    api.receive.side_effect = [None, {"dps": {"20": True}}]
    assert query_refreshed_dps(api, [20])["Err"] == "902"
    assert api.receive.call_count == 1
    assert_restored(api)


def test_real_error_preserved(api):
    error = {"Error": "unreachable", "Err": "905"}
    api.receive.return_value = error
    assert query_refreshed_dps(api, [20]) == error
    assert_restored(api)


def test_exception_restores_settings(api):
    api.receive.side_effect = RuntimeError("test receive failure")
    with pytest.raises(RuntimeError):
        query_refreshed_dps(api, [20])
    assert_restored(api)


def test_read_count_bound(api):
    api.receive.return_value = {"dps": {"20": True}}
    assert query_refreshed_dps(api, [20]) == {"dps": {"20": True}}
    assert api.receive.call_count == 8


def test_deadline_bound(api):
    with patch(
        "custom_components.tuya_local.helpers.dps_refresh.monotonic",
        side_effect=[0, 9],
    ):
        assert query_refreshed_dps(api, [20])["Err"] == "902"
    api.receive.assert_not_called()
    assert_restored(api)
