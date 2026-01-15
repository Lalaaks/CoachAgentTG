from __future__ import annotations

import asyncio


def main() -> None:
    """
    Backwards-compatible entrypoint.

    The actual Telegram bot runner lives in `app.ui.telegram.main`.
    """
    from app.ui.telegram.main import main as telegram_main

    asyncio.run(telegram_main())


if __name__ == "__main__":
    main()

