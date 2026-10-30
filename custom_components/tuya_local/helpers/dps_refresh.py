"""Explicit, bounded DPS refresh for devices that reject status queries."""

from select import select
from time import monotonic


def parse_refresh_dpids(value):
    """Parse an optional list without inventing DPS or probing other devices."""
    if not isinstance(value, str):
        raise ValueError("DPS must be a comma-separated string")
    if not value.strip():
        return []
    parts = value.split(",")
    if len(parts) > 32 or any(
        not part.strip().isascii() or not part.strip().isdigit() for part in parts
    ):
        raise ValueError("Enter up to 32 comma-separated DPS numbers")
    result = list(dict.fromkeys(int(part.strip()) for part in parts))
    if any(not 1 <= dp <= 255 for dp in result):
        raise ValueError("DPS numbers must be between 1 and 255")
    return result


def validate_refresh_dpids(value):
    """Validate a form value while keeping its stored representation stable."""
    parse_refresh_dpids(value)
    return value


def query_refreshed_dps(api, dpids):
    """Send one UPDATEDPS and collect actual reports on the same connection.

    Run in HA's executor, under the device API lock. This requests values;
    it never sends CONTROL or Wi-Fi configuration. Supported for direct devices.
    """
    persistent = api.socketPersistent
    timeout = api.connection_timeout
    retry = api.retry
    result = {}
    last_error = None
    try:
        api.set_socketPersistent(True)
        api.set_socketTimeout(min(timeout, 3))
        api.set_retry(False)
        response = api.updatedps(dpids, nowait=True)
        if isinstance(response, dict) and "Err" in response:
            return response
        deadline = monotonic() + 8
        for _ in range(8):
            remaining = deadline - monotonic()
            if remaining <= 0:
                break
            api.set_socketTimeout(min(timeout, 3, remaining))
            response = api.receive()
            if response is None:
                break
            if not isinstance(response, dict):
                continue
            if "Err" in response:
                last_error = response
                break
            dps = response.get("dps")
            if not isinstance(dps, dict):
                data = response.get("data")
                dps = data.get("dps") if isinstance(data, dict) else None
            if isinstance(dps, dict):
                result.update(dps)
        if result:
            return {"dps": result}
        return last_error or {
            "Error": "No DPS received after refresh request",
            "Err": "902",
            "Payload": None,
        }
    finally:
        api.set_retry(retry)
        api.set_socketTimeout(timeout)
        api.set_socketPersistent(persistent)


def receive_available_dps(api):
    """Read at most one ready message without waiting on an idle socket.

    Called by the persistent receiver while holding the API lock. Preserve
    TinyTuya's framing and socket timeout: a partly delivered frame must not
    be discarded by introducing a new, short socket timeout.
    """
    if api.socket is None:
        return None
    try:
        readable, _, _ = select([api.socket], [], [], 0)
    except OSError, ValueError:
        return {"Error": "Receive socket unavailable", "Err": "901", "Payload": None}
    if not readable:
        return None
    retry = api.retry
    try:
        # An empty ACK ends this read, not the connection or refresh request.
        api.set_retry(False)
        return api.receive()
    finally:
        api.set_retry(retry)
