from __future__ import annotations

from typing import Optional
from openai import AsyncOpenAI


class OpenAIClient:
    """
    OpenAI API client wrapper.
    """

    def __init__(self, api_key: Optional[str]) -> None:
        self._api_key = api_key
        self._client: Optional[AsyncOpenAI] = None
        if api_key:
            self._client = AsyncOpenAI(api_key=api_key)

    def is_available(self) -> bool:
        """Check if OpenAI is configured."""
        return self._client is not None

    async def analyze_tasks(
        self,
        completed_tasks: list[dict[str, str]],
        pending_tasks: list[dict[str, str]],
    ) -> str:
        """
        Analyze completed and pending tasks using OpenAI.

        Args:
            completed_tasks: List of completed tasks with 'title' field
            pending_tasks: List of pending tasks with 'title' field

        Returns:
            Analysis text in Finnish
        """
        if not self._client:
            return "OpenAI ei ole konfiguroitu. Lisää OPENAI_API_KEY .env-tiedostoon."

        # Build prompt
        completed_text = "\n".join(f"- {t.get('title', '')}" for t in completed_tasks) or "Ei tehtyjä tehtäviä."
        pending_text = "\n".join(f"- {t.get('title', '')}" for t in pending_tasks) or "Ei tekemättömiä tehtäviä."

        prompt = f"""Analysoi käyttäjän tehtäviä ja anna lyhyt, ystävällinen tulkinta suomeksi.

Tehdyt tehtävät:
{completed_text}

Tekemättömät tehtävät:
{pending_text}

Anna:
1. Lyhyt yhteenveto työnkulusta (mitä on tehty, mitä jäänyt)
2. Havaintoja työtapeista tai toistuvista teemoista
3. Ehdotus seuraavaksi tehtäväksi tai priorisointiin

Pidä vastaus lyhyenä ja käytännöllisenä (max 200 sanaa)."""

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Olet hyödyllinen henkilökohtainen avustaja, joka analysoi tehtäviä ja antaa käytännöllisiä havaintoja."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content or "Analyysi epäonnistui."
        except Exception as e:
            return f"OpenAI-virhe: {str(e)}"
