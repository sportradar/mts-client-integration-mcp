"""WebSocket frame reassembly for the frame_split scenario."""

from __future__ import annotations

import json

from mts_client_integration.models.business_rules import (
    MAX_FRAME_BYTES,
    MAX_FRAMES,
    MAX_MESSAGE_BYTES,
)


class FrameProtocolError(Exception):
    """Raised when frame constraints are violated; carries WebSocket close code."""

    def __init__(self, code: int, reason: str) -> None:
        self.code = code
        self.reason = reason
        super().__init__(reason)


class FrameAssembler:
    """Buffer WebSocket frames until a complete JSON message is received."""

    def __init__(self) -> None:
        self._frames: list[bytes] = []

    def reset(self) -> None:
        self._frames.clear()

    def feed(self, data: bytes | str) -> dict[str, object] | None:
        chunk = data if isinstance(data, bytes) else data.encode("utf-8")
        if len(chunk) > MAX_FRAME_BYTES:
            raise FrameProtocolError(
                1009,
                f"Single frame exceeds {MAX_FRAME_BYTES} bytes",
            )
        self._frames.append(chunk)
        if len(self._frames) > MAX_FRAMES:
            raise FrameProtocolError(1009, f"More than {MAX_FRAMES} frames")
        total = sum(len(frame) for frame in self._frames)
        if total > MAX_MESSAGE_BYTES:
            raise FrameProtocolError(
                1009,
                f"Total message exceeds {MAX_MESSAGE_BYTES} bytes",
            )
        payload = b"".join(self._frames)
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            raise FrameProtocolError(1009, "Message root must be a JSON object")
        self.reset()
        return parsed
