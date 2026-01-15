from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.infra.db.connection import Database
from app.infra.db.repo.scheduled_jobs_sqlite import ScheduledJobsRepo
from app.infra.ai.openai_client import OpenAIClient

router = Router()


def _agents_list_kb(agents: list[dict], openai_available: bool) -> InlineKeyboardMarkup:
    """Create keyboard for agent list."""
    kb = InlineKeyboardBuilder()

    for agent in agents:
        agent_id = agent["agent_id"]
        name = agent["name"]
        status_emoji = "🟢" if agent.get("is_active") else "⚪"
        kb.button(text=f"{status_emoji} {name}", callback_data=f"agent:view:{agent_id}")

    if openai_available:
        kb.button(text="🤖 Analysoi tehtäviä", callback_data="agent:analyze")

    kb.button(text="🔙 Takaisin", callback_data="agent:back")
    kb.adjust(1)
    return kb.as_markup()


async def _render_agent_info(agent: dict) -> str:
    """Render agent information."""
    agent_id = agent["agent_id"]
    name = agent["name"]
    category = agent.get("category", "unknown")
    is_active = agent.get("is_active", False)

    status = "🟢 Aktiivinen" if is_active else "⚪ Ei-aktiivinen"

    lines = [
        f"<b>{name}</b>",
        f"ID: <code>{agent_id}</code>",
        f"Kategoria: {category}",
        f"Tila: {status}",
    ]

    # Add description based on agent type
    if agent_id == "opp":
        lines.append("\n📝 Oppari-agentti auttaa työajan seurannassa.")
    elif agent_id == "system":
        lines.append("\n⚙️ System-agentti hoitaa järjestelmätehtäviä.")

    return "\n".join(lines)


@router.message(F.text == "Agentit")
async def agents_menu(message: Message, db: Database, openai_client: OpenAIClient | None):
    """Show agents menu."""
    rows = await db.fetchall(
        """
        SELECT agent_id, name, category, is_active
        FROM agents
        ORDER BY category, name;
        """,
    )

    if not rows:
        await message.answer("Ei agentteja rekisteröitynä.")
        return

    agents = [
        {
            "agent_id": r["agent_id"],
            "name": r["name"],
            "category": r["category"],
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]

    text = "<b>🤖 Agenttitoimisto</b>\n\nValitse agentti nähdäksesi lisätiedot."
    markup = _agents_list_kb(agents, openai_client.is_available() if openai_client else False)

    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("agent:view:"))
async def agent_view(cb: CallbackQuery, db: Database):
    """View specific agent details."""
    await cb.answer()
    if not cb.data:
        return
    agent_id = cb.data.split(":")[-1]

    row = await db.fetchone(
        """
        SELECT agent_id, name, category, is_active
        FROM agents
        WHERE agent_id = ?;
        """,
        (agent_id,),
    )

    if not row:
        await cb.message.answer("Agenttia ei löydy.")
        return

    agent = {
        "agent_id": row["agent_id"],
        "name": row["name"],
        "category": row["category"],
        "is_active": bool(row["is_active"]),
    }

    text = _render_agent_info(agent)

    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Takaisin", callback_data="agent:list")
    markup = kb.as_markup()

    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "agent:analyze")
async def agent_analyze(cb: CallbackQuery, jobs_repo: ScheduledJobsRepo, openai_client: OpenAIClient | None):
    """Analyze tasks using OpenAI."""
    await cb.answer()

    if not openai_client or not openai_client.is_available():
        await cb.message.answer("OpenAI ei ole käytettävissä. Lisää OPENAI_API_KEY .env-tiedostoon.")
        return

    user_id = cb.from_user.id

    # Show loading message
    await cb.message.edit_text("🤖 Analysoidaan tehtäviä...")

    # Get tasks
    pending = await jobs_repo.list_pending_todos(user_id)
    completed = await jobs_repo.list_completed_todos(user_id, limit=20)

    # Analyze
    analysis = await openai_client.analyze_tasks(completed, pending)

    # Show results
    text = f"<b>📊 Tehtävien analyysi</b>\n\n{analysis}"

    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Takaisin", callback_data="agent:list")
    markup = kb.as_markup()

    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "agent:list")
async def agent_list_back(cb: CallbackQuery, db: Database, openai_client: OpenAIClient | None):
    """Return to agent list."""
    await cb.answer()

    rows = await db.fetchall(
        """
        SELECT agent_id, name, category, is_active
        FROM agents
        ORDER BY category, name;
        """,
    )

    agents = [
        {
            "agent_id": r["agent_id"],
            "name": r["name"],
            "category": r["category"],
            "is_active": bool(r["is_active"]),
        }
        for r in rows
    ]

    text = "<b>🤖 Agenttitoimisto</b>\n\nValitse agentti nähdäksesi lisätiedot."
    markup = _agents_list_kb(agents, openai_client.is_available() if openai_client else False)

    await cb.message.edit_text(text, reply_markup=markup)


@router.callback_query(F.data == "agent:back")
async def agent_back(cb: CallbackQuery):
    """Return to main menu."""
    await cb.answer()
    from app.ui.telegram.keyboards.mainmenu import main_menu_kb
    await cb.message.answer("Päävalikko", reply_markup=main_menu_kb())