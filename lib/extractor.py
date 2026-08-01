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

    async def _extract_value(self, node: Node, field: SpecField) -> str | list[str]:
        if not field.selector:
            targets = [node]
        else:
            targets = node.css(field.selector)

        if not targets:
            return ""

        extracted_values = []
        for target in targets:
            if field.attribute == "text":
                val = target.text(strip=True)
            else:
                val = target.attributes.get(field.attribute, "").strip()

            if val:
                extracted_values.append(val)

        return extracted_values if len(extracted_values) > 1 else extracted_values[0]

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
                items[field.name] = await self._extract_value(parser, field)
            parsed_results.append(items)

        return parsed_results[0] if not schema.container else parsed_results
