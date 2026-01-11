from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class OutboundMessage:
    """
    Agentin tuottama ulosmenevä viesti.
    - text: viestin sisältö
    - reply_markup: aiogram InlineKeyboardMarkup tms (Optional)
    - silent: jos haluat myöhemmin tukea "disable_notification"
    """
    chat_id: int
    text: str
    reply_markup: Any | None = None
    silent: bool = False


@dataclass(frozen=True)
class AgentStatus:
    """
    Yhteinen statusnäkymä (vapaa sisältö).
    """
    title: str
    body: str
    reply_markup: Any | None = None


class AgentBase:
    """
    Yhteinen sopimus kaikille agenteille.
    - Agentti EI tiedä, kutsuiko sitä komento vai ajastus.
    - Agentti tuottaa OutboundMessage(ja) kun sille sanotaan "tick".
    """

    # sisäinen nimi (koodissa / db:ssä)
    key: str = "base"

    # käyttäjälle näkyvä nimi (UI:ssa)
    display_name: str = "Agentti"

    # mihin tyyppiin agentti kuuluu (hyödyllinen valikkoihin)
    kind: str = "generic"  # "process" | "service" | "reflective" | "generic"

    def __init__(self, db: Any):
        self.db = db

    async def ensure_schema(self) -> None:
        """
        Agenttikohtaiset taulut / migraatiot.
        Oletus: ei tee mitään, ellei agentti tarvitse.
        """
        return

    # ---- Komento / UI entrypoints ----

    async def help_text(self) -> str:
        """
        Lyhyt ohje agentin käytöstä. Tämä näkyy esim. /opp ilman alikomentoa.
        """
        return f"{self.display_name}: ei ohjetta."

    async def handle_command(self, chat_id: int, now: datetime, text: str) -> str | AgentStatus:
        """
        Komentopohjainen sisääntulo (esim. "/opp ..." tai "musiikki ...").
        Palauttaa joko tekstin tai AgentStatus (jos haluat mukana napit).
        """
        return "Ei toteutettu."

    # ---- Ajastetut / taustatarkistukset ----

    async def evaluate_tick(self, chat_id: int, now: datetime) -> list[OutboundMessage]:
        """
        Tätä kutsuu ajastuslooppi. Agentti päättää itse:
        - lähetetäänkö viestejä (muistutus, kysymys, kooste)
        - vai ei mitään ([])
        """
        return []

    # ---- Yhteinen status (valikko / katsaus) ----

    async def get_status(self, chat_id: int, now: datetime) -> AgentStatus:
        """
        Yhtenäinen statusrakenne.
        """
        return AgentStatus(title=self.display_name, body="Ei statusta.")
