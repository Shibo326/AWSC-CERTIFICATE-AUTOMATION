"""Unit tests for utils/network_monitor.py.

All network I/O is mocked — no real TCP connections are made during testing.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.network_monitor import NetworkMonitor


@pytest.fixture
def monitor() -> NetworkMonitor:
    """Create a fresh NetworkMonitor instance."""
    return NetworkMonitor()


# ---------- is_online() tests ----------


@pytest.mark.asyncio
async def test_is_online_returns_true_when_connection_succeeds(
    monitor: NetworkMonitor,
) -> None:
    """is_online returns True when TCP connection opens successfully."""
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("utils.network_monitor.asyncio.open_connection") as mock_open:
        mock_open.return_value = (MagicMock(), mock_writer)
        result = await monitor.is_online()

    assert result is True
    mock_writer.close.assert_called_once()
    mock_writer.wait_closed.assert_awaited_once()


@pytest.mark.asyncio
async def test_is_online_returns_false_on_timeout(
    monitor: NetworkMonitor,
) -> None:
    """is_online returns False when connection times out."""
    with patch("utils.network_monitor.asyncio.open_connection") as mock_open:
        mock_open.side_effect = asyncio.TimeoutError()
        result = await monitor.is_online()

    assert result is False


@pytest.mark.asyncio
async def test_is_online_returns_false_on_os_error(
    monitor: NetworkMonitor,
) -> None:
    """is_online returns False when an OSError occurs (e.g., no network)."""
    with patch("utils.network_monitor.asyncio.open_connection") as mock_open:
        mock_open.side_effect = OSError("Network is unreachable")
        result = await monitor.is_online()

    assert result is False


@pytest.mark.asyncio
async def test_is_online_returns_false_on_connection_refused(
    monitor: NetworkMonitor,
) -> None:
    """is_online returns False when connection is refused."""
    with patch("utils.network_monitor.asyncio.open_connection") as mock_open:
        mock_open.side_effect = ConnectionRefusedError()
        result = await monitor.is_online()

    assert result is False


@pytest.mark.asyncio
async def test_is_online_uses_correct_host_and_port(
    monitor: NetworkMonitor,
) -> None:
    """is_online connects to smtp.gmail.com:587."""
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("utils.network_monitor.asyncio.open_connection") as mock_open:
        mock_open.return_value = (MagicMock(), mock_writer)
        await monitor.is_online()

    mock_open.assert_called_once_with("smtp.gmail.com", 587)


@pytest.mark.asyncio
async def test_is_online_respects_timeout(monitor: NetworkMonitor) -> None:
    """is_online uses the configured TIMEOUT_SECONDS (5s)."""
    mock_writer = MagicMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("utils.network_monitor.asyncio.wait_for") as mock_wait_for:
        mock_wait_for.return_value = (MagicMock(), mock_writer)
        await monitor.is_online()

    # Verify the timeout kwarg was passed as 5
    _, kwargs = mock_wait_for.call_args
    assert kwargs["timeout"] == 5


# ---------- start_polling() / stop_polling() tests ----------


@pytest.mark.asyncio
async def test_start_polling_invokes_callback_on_initial_status(
    monitor: NetworkMonitor,
) -> None:
    """Polling invokes callback immediately on first status check."""
    callback = MagicMock()

    with patch.object(monitor, "is_online", new_callable=AsyncMock) as mock_online:
        mock_online.return_value = True

        await monitor.start_polling(callback)
        # Give the polling loop time to execute one iteration
        await asyncio.sleep(0.05)
        await monitor.stop_polling()

    callback.assert_called_with(True)


@pytest.mark.asyncio
async def test_start_polling_invokes_callback_on_status_change(
    monitor: NetworkMonitor,
) -> None:
    """Polling invokes callback when status transitions."""
    callback = MagicMock()
    call_count = 0

    async def mock_is_online() -> bool:
        nonlocal call_count
        call_count += 1
        # First call: online, second call: offline
        return call_count <= 1

    with patch.object(monitor, "is_online", side_effect=mock_is_online):
        # Use a short poll interval for testing
        monitor.POLL_INTERVAL_SECONDS = 0.01
        await monitor.start_polling(callback)
        await asyncio.sleep(0.1)
        await monitor.stop_polling()

    # Should have been called at least twice: True then False
    assert callback.call_count >= 2
    callback.assert_any_call(True)
    callback.assert_any_call(False)


@pytest.mark.asyncio
async def test_start_polling_does_not_invoke_callback_when_status_unchanged(
    monitor: NetworkMonitor,
) -> None:
    """Polling does NOT invoke callback when status stays the same."""
    callback = MagicMock()

    with patch.object(monitor, "is_online", new_callable=AsyncMock) as mock_online:
        mock_online.return_value = True
        monitor.POLL_INTERVAL_SECONDS = 0.01

        await monitor.start_polling(callback)
        await asyncio.sleep(0.1)
        await monitor.stop_polling()

    # Callback only invoked once (initial True), not on subsequent same-status checks
    callback.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_stop_polling_cancels_background_task(
    monitor: NetworkMonitor,
) -> None:
    """stop_polling cancels the background polling task."""
    callback = MagicMock()

    with patch.object(monitor, "is_online", new_callable=AsyncMock) as mock_online:
        mock_online.return_value = True
        monitor.POLL_INTERVAL_SECONDS = 0.01

        await monitor.start_polling(callback)
        await asyncio.sleep(0.05)
        await monitor.stop_polling()

    assert monitor._polling_task is None
    assert monitor._last_status is None


@pytest.mark.asyncio
async def test_stop_polling_when_not_polling_is_safe(
    monitor: NetworkMonitor,
) -> None:
    """stop_polling does nothing if no polling is active."""
    # Should not raise
    await monitor.stop_polling()
    assert monitor._polling_task is None


@pytest.mark.asyncio
async def test_start_polling_ignores_duplicate_start(
    monitor: NetworkMonitor,
) -> None:
    """Calling start_polling while already polling does not create a second task."""
    callback = MagicMock()

    with patch.object(monitor, "is_online", new_callable=AsyncMock) as mock_online:
        mock_online.return_value = True
        monitor.POLL_INTERVAL_SECONDS = 0.01

        await monitor.start_polling(callback)
        first_task = monitor._polling_task

        await monitor.start_polling(callback)
        second_task = monitor._polling_task

        await monitor.stop_polling()

    # Task should not have changed
    assert first_task is second_task


@pytest.mark.asyncio
async def test_polling_handles_callback_exception_gracefully(
    monitor: NetworkMonitor,
) -> None:
    """Polling continues even if callback raises an exception."""
    call_count = 0

    def failing_callback(status: bool) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Callback error")

    call_sequence = iter([True, False, True])

    async def mock_is_online() -> bool:
        return next(call_sequence, True)

    with patch.object(monitor, "is_online", side_effect=mock_is_online):
        monitor.POLL_INTERVAL_SECONDS = 0.01

        await monitor.start_polling(failing_callback)
        await asyncio.sleep(0.1)
        await monitor.stop_polling()

    # Despite the exception, polling continued and callback was invoked more times
    assert call_count >= 2
