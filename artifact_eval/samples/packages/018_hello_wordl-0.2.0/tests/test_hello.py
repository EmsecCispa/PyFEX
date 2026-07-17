"""Tests for the hello-wordl package."""

from hello_wordl.hello import hello


def test_hello_default():
    """Test the default greeting."""
    assert hello() == "Hello, wordl!"


def test_hello_with_name():
    """Test greeting with a name."""
    assert hello("Alice") == "Hello, Alice! Welcome to the wordl!"
