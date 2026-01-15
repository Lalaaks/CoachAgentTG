from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder


def stats_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🧠 Analyysi (7 päivää)", callback_data="stats:tasks:7")
    kb.button(text="🧠 Analyysi (30 päivää)", callback_data="stats:tasks:30")
    kb.adjust(1)
    return kb.as_markup()


def stats_result_kb(period_days: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Päivitä analyysi", callback_data=f"stats:tasks:{period_days}")
    kb.adjust(1)
    return kb.as_markup()
