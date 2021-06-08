from .cli import app
from .logging import set_logging_defaults


def main() -> None:
    """Start the CLI application."""
    set_logging_defaults()
    app()


if __name__ == "__main__":
    main()
