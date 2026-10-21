"""Tests for the pure helpers behind the weekly-report real-data summary."""
from app.services.analytics.period_summary import format_weekdays, short_name


def test_short_name():
    assert short_name("Grace Namukasa") == "Grace N."
    assert short_name("Mary Ann Okello") == "Mary O."
    assert short_name("Denis") == "Denis"
    assert short_name(None) == "Member"
    assert short_name("   ") == "Member"


def test_format_weekdays():
    assert format_weekdays([]) is None
    assert format_weekdays([0]) == "Mon"
    assert format_weekdays([3, 4, 5, 6]) == "Thu-Sun"
    assert format_weekdays([0, 4]) == "Mon, Fri"
    assert format_weekdays([6, 5, 3, 4, 0]) == "Mon, Thu-Sun"
    assert format_weekdays([1, 2]) == "Tue, Wed"
