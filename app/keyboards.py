from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Aloita opiskelu", callback_data="study:start")],
        [InlineKeyboardButton(text="📊 Tilastot", callback_data="stats:week")],
        [InlineKeyboardButton(text="⚙️ Asetukset", callback_data="settings:show")],
    ])

def minutes_kb(prefix: str) -> InlineKeyboardMarkup:
    # prefix e.g. "study:planned" or "study:done"
    mins = [15, 30, 45, 60, 90]
    row1 = [InlineKeyboardButton(text=str(m), callback_data=f"{prefix}:{m}") for m in mins[:3]]
    row2 = [InlineKeyboardButton(text=str(m), callback_data=f"{prefix}:{m}") for m in mins[3:]]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])

def scale_1_5(prefix: str) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=str(i), callback_data=f"{prefix}:{i}") for i in range(1, 6)]
    return InlineKeyboardMarkup(inline_keyboard=[row])

def reminder_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Aloita nyt", callback_data="remind:start_now")],
        [InlineKeyboardButton(text="⏰ Siirrä 30 min", callback_data="remind:snooze")],
        [InlineKeyboardButton(text="🚫 En tänään", callback_data="remind:not_today")],
    ])
