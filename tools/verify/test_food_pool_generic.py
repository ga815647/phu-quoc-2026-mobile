"""Generic pool rows keep identity without inventing place metadata."""
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_site import build_food_pool  # noqa: E402


class PoolCardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.food_ids = []
        self.names = []
        self.in_name = False
        self.map_links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-food-id' in attrs:
            self.food_ids.append(attrs['data-food-id'])
        if tag == 'div' and 'food-name' in attrs.get('class', '').split():
            self.in_name = True
        if tag == 'a' and 'map' in attrs.get('class', '').split():
            self.map_links.append(attrs.get('href'))

    def handle_data(self, data):
        if self.in_name:
            self.names.append(data)

    def handle_endtag(self, tag):
        if tag == 'div' and self.in_name:
            self.in_name = False


class GenericPoolTest(unittest.TestCase):
    def test_null_notion_uses_public_copy_without_changing_stable_id_or_inventing_map(self):
        rows = [
            {'pool_key': 'safari-inside', 'notion_id': None, 'pool_rank': 19,
             'order_copy': 'Safari 園內用餐', 'desc_copy': '餐點待現場確認'},
            {'pool_key': 'honthom-inside', 'notion_id': None, 'pool_rank': 20,
             'order_copy': '', 'desc_copy': '香島園內簡餐'},
        ]
        html, count = build_food_pool(rows, {}, {})
        parsed = PoolCardParser()
        parsed.feed(html)
        self.assertEqual(count, 2)
        self.assertEqual(parsed.food_ids, ['safari-inside', 'honthom-inside'])
        self.assertEqual(parsed.names, ['Safari 園內用餐', '香島園內簡餐'])
        self.assertEqual(parsed.map_links, [])


if __name__ == '__main__':
    unittest.main()
