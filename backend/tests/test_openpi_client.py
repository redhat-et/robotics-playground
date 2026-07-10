from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from robotics_playground.vendored import msgpack_numpy


@pytest.mark.anyio
async def test_openpi_client_connect_and_infer():
    from robotics_playground.policy.openpi_client import OpenPIClient

    mock_ws = MagicMock()
    # Server sends metadata on connect
    mock_ws.recv.side_effect = [
        msgpack_numpy.packb({"model": "dreamzero"}),  # metadata
        msgpack_numpy.packb({"actions": np.zeros((10, 8), dtype=np.float32)}),  # infer response
    ]

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        client = OpenPIClient("ws://localhost:8080/v1/realtime/robot/openpi")
        await client.connect()

        obs = {
            "observation/joint_position": np.zeros(7, dtype=np.float32),
            "prompt": "test",
        }
        result = await client.infer(obs)

        assert "actions" in result
        assert result["actions"].shape == (10, 8)
        mock_ws.send.assert_called_once()

        await client.close()
        mock_ws.close.assert_called_once()


@pytest.mark.anyio
async def test_openpi_client_infer_raises_on_string_response():
    from robotics_playground.policy.openpi_client import OpenPIClient

    mock_ws = MagicMock()
    mock_ws.recv.side_effect = [
        msgpack_numpy.packb({"model": "dreamzero"}),
        "Error: model not found",
    ]

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        client = OpenPIClient("ws://localhost:8080/v1/realtime/robot/openpi")
        await client.connect()

        with pytest.raises(RuntimeError, match="Error in inference server"):
            await client.infer({"prompt": "test"})

        await client.close()
