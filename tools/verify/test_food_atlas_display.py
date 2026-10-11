import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_site import build_food_pool, status_badge
class FoodAtlasDisplay(unittest.TestCase):
    def test_unknown_operating_date_does_not_use_review_date(self):
        out=status_badge({'atlas_state':'VERIFY','last_verified':None,'evidence_as_of':'2026-10-11'})
        self.assertIn('營運核實：未知',out)
        self.assertIn('資料查核 2026-10-11',out)
        self.assertNotIn('營運核實 2026-10-11',out)
    def test_priority_divider_is_neutral_without_reordering_pool(self):
        out,count=build_food_pool([{'pool_key':'held','pool_rank':1,'pool_role':'verify','divider':'主池｜這趟優先完成'}],{}, {})
        self.assertIn('候選清單｜依店家狀態選擇',out)
        self.assertNotIn('這趟優先完成',out)
        self.assertIn('data-food-id="held"',out)
