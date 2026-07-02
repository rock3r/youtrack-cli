"""Entry point: `python -m youtrack_cli` and the `yt` console script."""

from youtrack_cli.cli.app import app


def main() -> None:
    """Run the CLI."""
    app()


if __name__ == "__main__":
    main()
