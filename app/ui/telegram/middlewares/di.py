from __future__ import annotations

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.domain.oppari.service import OppariService
from app.infra.db.connection import Database
from app.infra.clock.system_clock import SystemClock


class DIMiddleware(BaseMiddleware):
    """
    Inject dependencies to handlers.
    """

    def __init__(
        self,
        oppari_service: OppariService,
        db: Database,
        clock: SystemClock,
        timezone: str,
    ):
        self._opp = oppari_service
        self._db = db
        self._clock = clock
        self._tz = timezone

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["opp_service"] = self._opp
        data["db"] = self._db
        data["clock"] = self._clock
        data["timezone"] = self._tz
        return await handler(event, data)
