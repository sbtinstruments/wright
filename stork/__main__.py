import logging

from .cli import app

_LOGGER = logging.getLogger()


def main() -> None:
    """Start the application."""
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("tftpy").setLevel(level=logging.INFO)
    app()


if __name__ == "__main__":
    main()
