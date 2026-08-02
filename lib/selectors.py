"""This file is the core of the extraction needs, and self-healing of the selectors."""

from pathlib import Path

from google import genai
from pydantic import BaseModel, Field

from lib.config import Config


class SpecField(BaseModel):
    """Speicifies the attributes of the field to be used for extraction."""

    name: str = Field(
        description="field name (e.g., 'title', 'url', 'author', 'chapter_text' and etc more.)"
    )
    selector: str = Field(description="the css selector targetting the element.")
    attribute: str = Field(
        default="text", description="the attribute of the targetted element."
    )


class SelectorSchema(BaseModel):
    """Speicifies the schema of the selectors to be used for extraction."""

    container: str | None = Field(
        default=None, description="the css selector container (null for single page)"
    )
    fields: list[SpecField]


class Selectors:
    """This class handles the core requirements of the extraction needs and the stability of the selectors."""

    def __init__(self):
        # this is a fixed path for all the selectors to be stored in the database.
        self.path = Path.cwd() / "selectors"
        self.config = Config()
        # the gemini client.
        self.client = genai.Client(api_key=self.config.get("api_key"))

    def __new__(cls) -> Selectors:
        """Ensures that only one instance of this class exists."""
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    async def _heal(self, key: str, html: str, required_fields: list[str]) -> None:
        """Heals the selectors for a given key using AI and writes them to the database."""

        # simple prompt to extract the selectors.
        prompt = f"""
        Target Page Key: '{key}'
        Required Fields to Extract: {required_fields}

        Raw HTML Snippet:
        {html}
        """

        # these are complex extraction rules for the model, to give as accurate results as possible.
        # i did not write them by hand, but rather tested and produced step by step using numerous results using an AI assitant.
        instruction = """
        You are a deterministic, production-grade CSS selector engine for web scrapers.

        CORE BEHAVIORAL DIRECTIVES:
        1. DETERMINISM & ZERO DRIFT: Output purely deterministic, minimal, and rock-solid selectors optimized for longevity across web layout updates.
        2. SYNTAX PURITY: Never output illegal CSS, unescaped utility characters, or unsupported pseudo-classes.
        3. SCHEMA CONFORMANCE: Output strictly valid JSON matching the specified schema with no markdown explanations or wrapped prose.

        SELECTOR GENERATION RULES:

        1. PAGE CLASSIFICATION:
        - LIST/GRID PAGES (e.g., search, updates, grids): Set 'container' to the repeating parent element targeting each card (e.g., `article.bg-base-300`). Inside containers, prefer direct utility selectors (e.g., `a.line-clamp-1`).
        - SINGLE ENTITY VIEWS (e.g., info/details pages, readers): Set 'container' to null.

        2. METADATA MATCHING (SINGLE / DETAILS PAGES):
        - For metadata links sharing identical styling classes on single-page views (where container is null), use full route attribute matching with query prefixes (e.g., `a[href*='search?author=']`, `a[href*='search?included_tag=']`).

        3. ANCHORED STRUCTURAL SELECTORS:
        - Scope positional text selectors to an explicit parent section or container ID (e.g., `section ul li:nth-child(5) > span`). Never leave positional selectors unanchored.

        4. NESTED SUB-LIST SCOPING:
        - When targeting sub-lists wrapped inside parent list items (`<li>`), scope through the parent `li` index first (e.g., `li:nth-child(2) > ul.list-disc > li`). NEVER use `:nth-of-type()` directly on a nested sub-list if each sub-list is wrapped in its own individual parent `li`.

        5. SCALAR FIELDS:
        - For single scalar fields (e.g., 'latest chapter'), target exact inner paths using `:first-child` (e.g., `#chapter-list > div:first-child span.grow > span:first-child`).

        6. FORBID TAILWIND SPECIAL CHARACTERS:
        - NEVER use utility classes containing colons ':', slashes '/', brackets '[]', or percentages '%' (e.g., FORBID 'md:w-4/12', 'hover:bg-red', 'w-1/2').

        7. ATTRIBUTE HANDLING:
        - Set 'attribute' to 'text' for text content, or specific HTML attributes like 'href', 'src', etc.
        """

        print(f"repairing extractor for {key} page, please wait.")

        response = self.client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                response_schema=SelectorSchema,
                temperature=0.0,
            ),
        )

        # the response is a json, we then parse it to a SelectorSchema object and write it to the database.
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

        # case: selectors don't exist in the database, so heal them and re-run our process.
        await self._heal(key, html, required_fields=fields)
        return await self.fetch(key, html, fields)

    def invalidate(self, key: str) -> None:
        """invalidates the selectors for a given key."""
        file = (self.path / key).with_suffix(".json")
        if file.exists():
            file.unlink(missing_ok=True)
