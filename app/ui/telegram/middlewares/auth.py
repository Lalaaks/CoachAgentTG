from __future__ import annotations

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable


class OwnerOnlyMiddleware(BaseMiddleware):
    def __init__(self, owner_id: int):
        self._owner_id = owner_id

    async def __call__(
        self,
        handler: Callable,
        event,
        data: Dict[str, Any],
    ):
        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id != self._owner_id:
            return  # silently ignore

        return await handler(event, data)
