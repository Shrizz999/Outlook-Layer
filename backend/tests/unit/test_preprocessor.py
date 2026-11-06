"""Unit tests for EmailPreprocessor."""
import pytest
from app.services.email.preprocessor import EmailPreprocessor


def test_clean_single_message():
    preprocessor = EmailPreprocessor()
    body = "Hello,\nPlease confirm delivery for SO-1025.\nThanks,\nJohn"
    res = preprocessor.preprocess(body, sender_address="john@example.com")
    assert "Please confirm delivery for SO-1025." in res.cleaned_body
    assert res.quoted_history is None
    assert not res.is_automated
    assert res.body_hash is not None


def test_split_quoted_history_on_wrote():
    preprocessor = EmailPreprocessor()
    body = (
        "We agree with the revised delivery date.\n\n"
        "On 01 Nov 2026, at 14:00, procurement@acme.com wrote:\n"
        "> Can you expedite shipment to 20 November?\n"
    )
    res = preprocessor.preprocess(body)
    assert "We agree with the revised delivery date." in res.cleaned_body
    assert "On 01 Nov 2026" in res.quoted_history
    assert "> Can you expedite shipment" in res.quoted_history


def test_split_quoted_history_outlook_style():
    preprocessor = EmailPreprocessor()
    body = (
        "Acknowledged, thank you.\n\n"
        "-----Original Message-----\n"
        "From: Alice Purchase\n"
        "Sent: 02 Nov 2026\n"
        "To: Bob Sales\n"
        "Subject: Order update\n"
        "Material has arrived.\n"
    )
    res = preprocessor.preprocess(body)
    assert res.cleaned_body == "Acknowledged, thank you."
    assert "Original Message" in res.quoted_history
    assert "Material has arrived." in res.quoted_history


def test_detect_automated_notification():
    preprocessor = EmailPreprocessor()
    body = "Your report has been generated. This is an automated message."
    res = preprocessor.preprocess(body, sender_address="noreply@system.invalid")
    assert res.is_automated is True


def test_empty_body():
    preprocessor = EmailPreprocessor()
    res = preprocessor.preprocess(None)
    assert res.cleaned_body == ""
    assert res.quoted_history is None
    assert res.is_automated is False
