from __future__ import annotations

import logging

import pytest

from connectors.protocols import ProtocolValidationError
from connectors.protocols.mqtt import (
    MQTTS_DEFAULT_PORT,
    MqttConnectorConfig,
    MqttProtocolConnector,
    normalize_mqtt_target,
)
from connectors.protocols.websocket_connector import (
    WSS_DEFAULT_PORT,
    WebSocketConnectorConfig,
    WebSocketProtocolConnector,
    normalize_ws_target,
)


def test_mqtt_targets_are_tls_by_default() -> None:
    host, port, tls = normalize_mqtt_target("broker.example.test")

    assert host == "broker.example.test"
    assert port == MQTTS_DEFAULT_PORT
    assert tls is True


def test_mqtt_plaintext_requires_explicit_governance_opt_in(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ProtocolValidationError, match="allow_plaintext"):
        MqttProtocolConnector(MqttConnectorConfig(target="mqtt://broker.example.test:1883"))

    caplog.set_level(logging.WARNING)
    connector = MqttProtocolConnector(
        MqttConnectorConfig(target="mqtt://broker.example.test:1883", allow_plaintext=True)
    )

    info = connector.info()
    assert info.meta["tls"] is False
    assert info.meta["allow_plaintext"] is True
    assert any("Plaintext MQTT enabled" in record.message for record in caplog.records)


def test_websocket_targets_are_tls_by_default() -> None:
    target = normalize_ws_target("socket.example.test/stream")

    assert target["url"] == "wss://socket.example.test/stream"
    assert target["port"] == WSS_DEFAULT_PORT
    assert target["tls"] is True


def test_websocket_plaintext_requires_explicit_governance_opt_in(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ProtocolValidationError, match="allow_plaintext"):
        WebSocketProtocolConnector(WebSocketConnectorConfig(target="ws://socket.example.test"))

    caplog.set_level(logging.WARNING)
    connector = WebSocketProtocolConnector(
        WebSocketConnectorConfig(target="ws://socket.example.test", allow_plaintext=True)
    )

    info = connector.info()
    assert info.meta["tls"] is False
    assert info.meta["allow_plaintext"] is True
    assert any("Plaintext WebSocket enabled" in record.message for record in caplog.records)
