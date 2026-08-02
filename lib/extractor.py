"""Smart extractor for parsing content using stored selectors."""

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
        """The main function to handle the whole extraction process."""
        html = parser.html.strip()

        # fetches the selectors from their key file json and returns the schema for the extraction
        selector_schema = await self.selectors.fetch(key, html, fields)
        results = await self._parse(parser, selector_schema)

        if self._is_valid_extraction(results, fields):
            # safe check to ensure that we have valid results.
            return results

        # oops.. seems like we got invalid results, let's dump current selectors and fetch new ones.
        self.selectors.invalidate(key)
        return await self.extract(key, parser, fields)

    def _is_valid_extraction(
        self, results: list[dict[str, str]], required_fields: list[str]
    ) -> bool:
        """Checks if the results are valid by ensuring that all the required fields are present."""
        if not results:
            return False

        for result in results:
            for field in required_fields:
                if not result.get(field):
                    # hmm, one field is missing, this is invalid.
                    return False

        return True

    async def _extract_value(self, node: Node, field: SpecField) -> str | list[str]:
        """Smartly extracts the value from the node based on the field's selector and attribute."""
        if not field.selector:
            targets = [node]
        else:
            targets = node.css(field.selector)

        if not targets:
            return ""

        extracted_values = []
        for target in targets:
            if field.attribute == "text":
                value = target.text(strip=True)
            else:
                value = target.attributes.get(field.attribute, "").strip()

            if value:
                extracted_values.append(value)

        return extracted_values if len(extracted_values) > 1 else extracted_values[0]

    async def _parse(
        self, parser: HTMLParser, schema: SelectorSchema
    ) -> list[dict[str, str]]:
        """Parses the content using the provided schema and extracts the data accordingly."""
        parsed_results = []

        # item can refer to manga, manga-pages, manga-details.

        # case 1: The page holds multiple item results.
        if schema.container:
            for card in parser.css(schema.container):
                items = {}
                for field in schema.fields:
                    items[field.name] = await self._extract_value(card, field)
                parsed_results.append(items)

        # case 2: The page holds a single item result.
        else:
            items = {}
            for field in schema.fields:
                items[field.name] = await self._extract_value(parser, field)
            parsed_results.append(items)

        return parsed_results[0] if not schema.container else parsed_results
