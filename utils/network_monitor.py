"""Network connectivity monitor for CertFlow.

Provides TCP-based network probing to smtp.gmail.com:587 and optional
background polling with status-change callbacks.
"""

import asyncio
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class NetworkMonitor:
    """Check network connectivity via TCP probe to SMTP server.

    Uses a non-blocking TCP connection attempt to determine whether the
    SMTP server is reachable. Supports background polling that invokes a
    callback only when the online/offline status changes.

    Attributes:
        SMTP_HOST: Target host for the connectivity probe.
        SMTP_PORT: Target port for the connectivity probe.
        TIMEOUT_SECONDS: Maximum wait time for the TCP connection.
        POLL_INTERVAL_SECONDS: Seconds between consecutive polling checks.
    """

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    TIMEOUT_SECONDS: int = 5
    POLL_INTERVAL_SECONDS: int = 30

    def __init__(self) -> None:
        """Initialize the NetworkMonitor with no active polling."""
        self._polling_task: Optional[asyncio.Task] = None
        self._last_status: Optional[bool] = None

    async def is_online(self) -> bool:
        """Attempt a TCP connection to the SMTP server.

        Returns:
            True if the connection succeeds within the timeout, False otherwise.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.SMTP_HOST, self.SMTP_PORT),
                timeout=self.TIMEOUT_SECONDS,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except (OSError, asyncio.TimeoutError, ConnectionRefusedError):
            return False

    async def start_polling(self, callback: Callable[[bool], None]) -> None:
        """Start background polling that invokes callback on status change.

        Checks connectivity every POLL_INTERVAL_SECONDS. The callback is
        only invoked when the status transitions between online and offline
        (not on every check).

        Args:
            callback: A callable that receives a bool indicating the new
                connectivity status (True = online, False = offline).
        """
        if self._polling_task is not None and not self._polling_task.done():
            logger.warning("Polling is already active; ignoring start request.")
            return

        self._last_status = None

        async def _poll_loop() -> None:
            while True:
                current_status = await self.is_online()
                if current_status != self._last_status:
                    self._last_status = current_status
                    try:
                        callback(current_status)
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "Polling callback raised an exception: %s", exc
                        )
                await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

        self._polling_task = asyncio.create_task(_poll_loop())

    async def stop_polling(self) -> None:
        """Cancel the background polling task.

        If no polling task is active, this method does nothing.
        """
        if self._polling_task is not None and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        self._polling_task = None
        self._last_status = None
