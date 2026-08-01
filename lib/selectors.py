from pathlib import Path

from google import genai
from pydantic import BaseModel, Field


class SpecField(BaseModel):
    name: str = Field(
        description="field name (e.g., 'title', 'url', 'author', 'chapter_text' and etc more.)"
    )
    selector: str = Field(description="the css selector targetting the element.")
    attribute: str = Field(
        default="text", description="the attribute of the targetted element."
    )


class SelectorSchema(BaseModel):
    container: str | None = Field(
        default=None, description="the css selector container (null for single page)"
    )
    fields: list[SpecField]


class Selectors:
    def __init__(self):
        self.path = Path.cwd() / "selectors"
        self.client = genai.Client()

    def __new__(cls) -> Selectors:
        """Ensures that only one instance of this class exists."""
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _heal(self, key: str, html: str, required_fields: list[str]) -> None:
        prompt = f"""
        Analyze this HTML snippet for a '{key}' page.
        Create CSS selector rules to extract the following fields: {required_fields}.

        Rules:
        - If this page displays a LIST/GRID of repeating items (e.g., search results, updates, cards), set 'container' to the repeating parent element targeting each card.
        - If this page is a SINGLE entity view (e.g., info page, reader), set 'container' to null.
        - Set 'attribute' to 'text' for text content, or specific HTML attributes like 'href', 'src', etc.

        CSS SELECTOR FORMAT RULES (STRICT):
        1. REPEATING CONTAINERS (SEARCH / GRID PAGES):
           - For list/grid pages, ALWAYS combine the repeating element tag with its primary identifying class for 'container' (e.g., `article.bg-base-300` instead of plain `article`).
           - Inside card containers, prefer direct utility class selectors (e.g., `a.line-clamp-1`) over complex ancestor chains or unnecessary attribute matches.

        2. METADATA ATTRIBUTE MATCHING (SINGLE / DETAILS PAGES):
           - For metadata links sharing identical styling classes on single-page views (where container is null), use full route attribute matching (e.g., `a[href*='search?author=']`, `a[href*='search?included_tag=']`). Include the route prefix (e.g. 'search?').

        3. ANCHOR STRUCTURAL SELECTORS:
           - Scope positional text selectors to an explicit parent section or container ID (e.g., `section ul li:nth-child(5) > span` instead of unanchored `ul > li:nth-child(5)`).

        4. NESTED SUB-LIST SCOPING:
           - When targeting sub-lists wrapped inside parent list items (`<li>`), scope through the parent `li` index first (e.g., `li:nth-child(2) > ul.list-disc > li`). NEVER use `:nth-of-type()` directly on a nested sub-list if each sub-list is wrapped in its own individual parent `li`.

        5. SCALAR FIELDS:
           - For single scalar fields (e.g., 'latest chapter'), target exact inner paths using `:first-child` (e.g., `#chapter-list > div:first-child span.grow > span:first-child`).

        6. FORBID TAILWIND SPECIAL CHARACTERS:
           - NEVER use utility classes containing colons ':', slashes '/', brackets '[]', or percentages '%' (e.g., FORBID 'md:w-4/12', 'hover:bg-red', 'w-1/2').
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
                temperature=0.0,  # Low temperature ensures strict compliance with facts and schema
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
        """fetches the selectors from database, heals using ai if selectors don't exist in the database."""
        selector_schema = self.load(key=key)
        if selector_schema:
            return selector_schema

        # this means that the selectors need to be healed

        await self._heal(key, html, required_fields=fields)
        return await self.fetch(key, html, fields)
