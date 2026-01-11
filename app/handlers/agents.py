# app/handlers/agents.py

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()

# MVP: tunnetut agentit + lyhyt kuvaus (päivitä vapaasti)
AGENTS_INFO: dict[str, str] = {
    "study": "Opiskelusessiot ja reflektio (/study, /end, /stats).",
    "health": "Hyvinvointi: uni, liikunta, ruoka (tulossa).",
    "productivity": "Tavoitteet, päivän fokus, tekemisen ohjaus (tulossa).",
    "finance": "Kulutuksen seuranta ja talousmuistiot (tulossa).",
    "social": "Sosiaalinen elämä ja yhteydenpito (tulossa).",
    "mindset": "Ajattelu, mieliala, itsearviointi (tulossa).",
}


def _is_owner(message: Message, config) -> bool:
    return message.from_user.id == config.owner_telegram_id


def _normalize_agent(name: str) -> str:
    return name.strip().lower()


@router.message(Command("agents"))
async def cmd_agents(message: Message, db, config):
    if not _is_owner(message, config):
        return await message.answer("Tämä botti on rajattu omistajalle.")

    active = await db.get_active_agents(message.from_user.id)
    active_set = set(active)

    lines = ["🤖 AGENTIT\n"]

    # Näytä tunnetut agentit + status
    lines.append("Saatavilla:")
    for a in sorted(AGENTS_INFO.keys()):
        mark = "✅" if a in active_set else "⛔"
        lines.append(f"{mark} {a} – {AGENTS_INFO[a]}")

    # Näytä myös mahdolliset tuntemattomat (db:ssä) agentit
    unknown_active = sorted(active_set - set(AGENTS_INFO.keys()))
    if unknown_active:
        lines.append("\nMuut aktiiviset (ei kuvauksia):")
        lines.extend([f"✅ {a}" for a in unknown_active])

    lines.append(
        "\nKäyttö:\n"
        "/agent_add <nimi>\n"
        "/agent_remove <nimi>\n"
        "/agent_enable <nimi>\n"
        "/agent_disable <nimi>\n"
        "/agent_info <nimi>"
    )

    await message.answer("\n".join(lines))


@router.message(Command("agent_add"))
async def cmd_agent_add(message: Message, db, config):
    if not _is_owner(message, config):
        return await message.answer("Tämä botti on rajattu omistajalle.")

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Anna agentin nimi. Esim: /agent_add health")

    agent = _normalize_agent(parts[1])
    await db.set_agent_enabled(message.from_user.id, agent, True)

    desc = AGENTS_INFO.get(agent, "Ei kuvausta (MVP).")
    await message.answer(f"✅ Agentti lisätty ja aktivoitu: {agent}\nℹ️ {desc}")


@router.message(Command("agent_remove"))
async def cmd_agent_remove(message: Message, db, config):
    if not _is_owner(message, config):
        return await message.answer("Tämä botti on rajattu omistajalle.")

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Anna agentin nimi. Esim: /agent_remove health")

    agent = _normalize_agent(parts[1])
    await db.remove_agent(message.from_user.id, agent)
    await message.answer(f"🗑️ Agentti poistettu: {agent}")


@router.message(Command("agent_enable"))
async def cmd_agent_enable(message: Message, db, config):
    if not _is_owner(message, config):
        return await message.answer("Tämä botti on rajattu omistajalle.")

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Anna agentin nimi. Esim: /agent_enable health")

    agent = _normalize_agent(parts[1])
    await db.set_agent_enabled(message.from_user.id, agent, True)
    await message.answer(f"✅ Agentti aktivoitu: {agent}")


@router.message(Command("agent_disable"))
async def cmd_agent_disable(message: Message, db, config):
    if not _is_owner(message, config):
        return await message.answer("Tämä botti on rajattu omistajalle.")

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Anna agentin nimi. Esim: /agent_disable health")

    agent = _normalize_agent(parts[1])
    await db.set_agent_enabled(message.from_user.id, agent, False)
    await message.answer(f"⛔ Agentti pois päältä: {agent}")


@router.message(Command("agent_info"))
async def cmd_agent_info(message: Message, db, config):
    if not _is_owner(message, config):
        return await message.answer("Tämä botti on rajattu omistajalle.")

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("Anna agentin nimi. Esim: /agent_info health")

    agent = _normalize_agent(parts[1])
    active = await db.get_active_agents(message.from_user.id)
    is_active = agent in set(active)

    desc = AGENTS_INFO.get(agent, "Ei kuvausta (MVP).")
    status = "✅ aktiivinen" if is_active else "⛔ ei aktiivinen"

    await message.answer(
        f"ℹ️ Agentti: {agent}\n"
        f"Status: {status}\n"
        f"Kuvaus: {desc}\n\n"
        f"Nopeasti:\n"
        f"/agent_enable {agent}\n"
        f"/agent_disable {agent}\n"
        f"/agent_remove {agent}"
    )
