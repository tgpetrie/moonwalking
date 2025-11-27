"""Compatibility wrapper for the historical standalone sentiment script."""

from backend.sentiment_api import app, main

__all__ = ["app"]


if __name__ == "__main__":
    main()
