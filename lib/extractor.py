from selectolax.parser import HTMLParser, Node

from lib.selectors import Selectors, SelectorSchema, SpecField


class Extractor:
    """used for extracting the data from the parser"""

    def __init__(self):
        self.selectors: Selectors = Selectors()

    def __new__(cls) -> Extractor:
        """Ensures that only one instance of this class exists."""
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    async def extract(
        self, key: str, parser: HTMLParser, fields: list[str]
    ) -> list[dict[str, str]]:
        html = parser.html.strip()
        selector_schema = await self.selectors.fetch(key, html, fields)
        results = await self._parse(parser, selector_schema)
        return results

    async def _extract_value(self, node: Node, field: SpecField) -> str:
        target = node.css_first(field.selector) if field.selector else node
        if not target:
            return ""

        if field.attribute == "text":
            return target.text(strip=True)
        return target.attributes.get(field.attribute, "").strip()

    async def _parse(
        self, parser: HTMLParser, schema: SelectorSchema
    ) -> list[dict[str, str]]:
        parsed_results = []

        if schema.container:
            for card in parser.css(schema.container):
                items = {}
                for field in schema.fields:
                    items[field.name] = await self._extract_value(card, field)
                parsed_results.append(items)

        else:
            items = {}
            for field in schema.fields:
                items[field.name] = await self._extract_value(parser.root, field)
            parsed_results.append(items)

        return parsed_results
