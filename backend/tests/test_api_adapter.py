"""Tests for the API acquisition adapter."""

from app.acquisition.api_adapter import _parse_link_header


class TestParseLinkHeader:
    def test_valid_next_link(self):
        header = '<https://api.example.com/page2>; rel="next"'
        assert _parse_link_header(header) == "https://api.example.com/page2"

    def test_multiple_links(self):
        header = (
            '<https://api.example.com/page1>; rel="prev", '
            '<https://api.example.com/page3>; rel="next"'
        )
        assert _parse_link_header(header) == "https://api.example.com/page3"

    def test_no_next_link(self):
        header = '<https://api.example.com/page1>; rel="prev"'
        assert _parse_link_header(header) is None

    def test_empty_header(self):
        assert _parse_link_header("") is None
