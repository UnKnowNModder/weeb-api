import asyncio
from pathlib import Path
from google import genai
from pydantic import BaseModel, Field

class SpecField(BaseModel):
    name: str = Field(description="field name (e.g., 'title', 'url', 'author', 'chapter_text' and etc more.)")
    selector: str = Field(description="the css selector targetting the element.")
    attribute: str = Field(default="text", description="the attribute of the targetted element.")

class SelectorSchema(BaseModel):
    container: str | None = Field(default=None, description="the css selector container (null for single page)")
    fields: list[SpecField]

class Selectors:
    def __init__(self):
        self.path = Path.cwd() / "selectors"
        self.client = genai.Client()

    def __new__(cls) -> Selectors:
        """Ensures that only one instance of this class exists."""
        if not hasattr(cls, "_instance"):
            cls._instance = super(Selectors, cls).__new__(cls)
        return cls._instance

    async def _heal(self, key: str, html: str, required_fields: list[str]) -> None:
        prompt = f"""
        Analyze this HTML snippet for a '{key}' page.
        Create CSS selector rules to extract the following fields: {required_fields}.

        Rules:
        - If this page displays a LIST/GRID of cards (e.g., search, updates, chapters), set 'container' to the repeating CSS selector targeting each card.
        - If this page is a SINGLE page (e.g., synopsis/info page), set 'container' to null.
        - Set 'attribute' to 'text' for text content, or specific HTML attributes like 'href', 'src', etc.

        CSS SELECTOR FORMAT RULES (STRICT):
        1. ALWAYS PREFER CLASSES: Target elements using their HTML `class` attributes first (including utility classes like `a.line-clamp-1`, `.title-text`, `.font-bold`, etc.).
        2. USE TAG + CLASS: Combine the HTML element tag with its primary class when available (e.g., `a.line-clamp-1` instead of just `.line-clamp-1`).
        3. ATTRIBUTE SELECTORS AS LAST RESORT ONLY: Do NOT use attribute substring matching like `a[href*='/series/']` or `[src*='...']` UNLESS the element has absolutely no class attribute.

        Raw HTML:
        {html}
        """
        instruction = "You are an expert CSS selector engine for web scrapers."

        print(f"repairing extractor for {key} page, please wait.")

        response = self.client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                response_schema=SelectorSchema,
                temperature=0.0, # Low temperature ensures strict compliance with facts and schema
            ),
        )

        schema = response.parsed
        self.write(key, schema)
        print("successfully repaired")


    def load(self, key: str) -> SelectorSchema | None:
        file = (self.path / key).with_suffix(".json")
        if file.exists():
            raw_json = file.read_text(encoding="utf-8")
            data = SelectorSchema.model_validate_json(raw_json)
            return data

    def write(self, key: str, data: SelectorSchema) -> None:
        file = (self.path / key).with_suffix(".json")
        data = data.model_dump_json(indent=4)
        file.write_text(data=data, encoding="utf-8")

    async def fetch(self, key: str, html: str, fields: list[str]):
        """ fetches the selectors from database, heals using ai if selectors don't exist in the database."""
        selector_schema = self.load(key=key)
        if selector_schema:
            return selector_schema

        # this means that the selectors need to be healed

        await self._heal(key, html, required_fields=fields)
        return await self.fetch(key, html, fields)
