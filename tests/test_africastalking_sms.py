import importlib
from unittest.mock import Mock

import pytest

sms_helper = importlib.import_module(
    "app.services.communication.sms.helpers.send_sms"
)


@pytest.mark.parametrize("status_code", [100, 101, 102])
def test_send_sms_returns_true_when_provider_accepts_recipient(
    monkeypatch, status_code
):
    provider = Mock(
        send=Mock(
            return_value={
                "SMSMessageData": {
                    "Recipients": [{"statusCode": status_code}],
                }
            }
        )
    )
    monkeypatch.setattr(sms_helper, "sms", provider)

    assert sms_helper.send_sms("0771234567", "Test message") is True
    provider.send.assert_called_once_with("Test message", ["+256771234567"])


def test_send_sms_returns_false_when_provider_rejects_recipient(monkeypatch):
    provider = Mock(
        send=Mock(
            return_value={
                "SMSMessageData": {
                    "Recipients": [{"statusCode": 403}],
                }
            }
        )
    )
    monkeypatch.setattr(sms_helper, "sms", provider)

    assert sms_helper.send_sms("+256771234567", "Test message") is False


@pytest.mark.parametrize("response", [None, {}, {"SMSMessageData": {}}])
def test_send_sms_returns_false_for_unrecognized_provider_response(
    monkeypatch, response
):
    monkeypatch.setattr(sms_helper, "sms", Mock(send=Mock(return_value=response)))

    assert sms_helper.send_sms("+256771234567", "Test message") is False


def test_send_sms_returns_false_when_provider_request_raises(monkeypatch):
    provider = Mock(send=Mock(side_effect=RuntimeError("provider unavailable")))
    monkeypatch.setattr(sms_helper, "sms", provider)

    assert sms_helper.send_sms("+256771234567", "Test message") is False
