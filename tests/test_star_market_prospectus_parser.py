import unittest
from dataclasses import dataclass

from tools import star_market_prospectus_parser as parser


@dataclass(frozen=True)
class Page:
    number: int
    text: str


class ConservativeStarParserTests(unittest.TestCase):
    def _pages(self) -> list[Page]:
        return [
            Page(
                21,
                """
                第一节 释义
                中科算源 指 北京中科算源资产管理有限公司
                古生代创投 指 苏州工业园区古生代创业投资企业（有限合伙）
                国投基金 指 国投（上海）科技成果转化创业投资基金企业（有限合伙）
                南京招银 指
                南京招银电信新趋势凌霄成长股权投资基金合伙企业（有限合伙），
                曾用名为深圳招银电信新趋势凌霄成长股权投资基金合伙企业（有限合伙）
                """,
            ),
            Page(
                90,
                """
                5、国投基金
                名称 国投（上海）科技成果转化创业投资基金企业（有限合伙）
                企业类型 有限合伙企业
                执行事务合伙人 国投（上海）创业投资管理有限公司
                住所 上海市杨浦区控江路 1142 号 23 幢 4064-31 室
                认缴出资额（万元） 1,000,000.00
                成立日期 2016 年 3 月 4 日
                主营业务 股权投资业务
                6、宁波瀚高
                """,
            ),
            Page(
                93,
                """
                十、发行人股本情况
                （一）公司本次发行前后公司股本情况
                序号 股东名称/姓名 本次发行前 本次发行后
                持股数（股） 占比（%） 持股数（股） 占比（%）
                1 陈天石 119,497,756 33.19 119,497,756 29.87
                2 中科算源（SS） 65,669,721 18.24 65,669,721 16.41
                3 古生代创投 14,151,905 3.93 14,151,905 3.54
                4 国投基金 14,124,730 3.92 14,124,730 3.53
                5 南京招银 13,002,264 3.61 13,002,264 3.25
                1 南京原点正则创业投资管理中心（有限合伙） 普通合伙人 100.00 0.51
                """,
            ),
            Page(
                94,
                """
                序号 股东名称/姓名
                本次发行前 本次发行后
                持股数（股） 占比（%） 持股数（股） 占比（%）
                6 整体变更为股份有限公司 4,000,000 1.00 4,000,000 0.90
                7 管理有限公司 3,000,000 0.80 3,000,000 0.70
                本次发行前的前十名股东
                序号 股东名称/姓名 股份（股） 比例（%）
                4 国投基金 14,124,730 3.92
                """,
            ),
        ]

    def test_primary_shareholder_table_requires_pre_and_post_columns(self):
        rows = parser.parse_shareholder_rows(self._pages())
        names = [row.disclosed_name for row in rows]
        self.assertIn("国投基金", names)
        self.assertNotIn("南京原点正则创业投资管理中心（有限合伙）", names)
        self.assertNotIn("整体变更为股份有限公司", names)
        self.assertEqual(names.count("国投基金"), 1)

    def test_same_row_holding_values_are_not_polluted_by_nearby_percentages(self):
        investors = parser.extract_institutional_investors(
            self._pages(),
            "寒武纪",
            max_investors=20,
        )
        fund = next(item for item in investors if item.get("disclosedName") == "国投基金")
        self.assertEqual(fund["preIpoShares"], 14124730)
        self.assertEqual(fund["preIpoOwnershipPct"], 3.92)
        self.assertEqual(fund["sourcePage"], 93)
        self.assertEqual(fund["evidence"], "4 国投基金 14,124,730 3.92 14,124,730 3.53")

    def test_definitions_restore_full_legal_names_and_exclude_natural_people(self):
        investors = parser.extract_institutional_investors(
            self._pages(),
            "寒武纪",
            max_investors=20,
        )
        names = [item["name"] for item in investors]
        self.assertNotIn("陈天石", names)
        self.assertIn("北京中科算源资产管理有限公司", names)
        self.assertIn("苏州工业园区古生代创业投资企业（有限合伙）", names)
        self.assertIn(
            "南京招银电信新趋势凌霄成长股权投资基金合伙企业（有限合伙）",
            names,
        )

    def test_contact_is_only_taken_from_the_exact_institution_basic_information_block(self):
        investors = parser.extract_institutional_investors(
            self._pages(),
            "寒武纪",
            max_investors=20,
        )
        fund = next(item for item in investors if item.get("disclosedName") == "国投基金")
        self.assertEqual(
            fund["publicContact"]["officeAddress"],
            "上海市杨浦区控江路 1142 号 23 幢 4064-31 室",
        )
        self.assertEqual(fund["publicContact"]["sourcePage"], 90)
        nanjing = next(item for item in investors if item.get("disclosedName") == "南京招银")
        self.assertEqual(nanjing["contactStatus"], "not-disclosed-in-prospectus")
        self.assertNotIn("publicContact", nanjing)

    def test_generic_and_narrative_names_never_enter_the_directory(self):
        investors = parser.extract_institutional_investors(
            self._pages(),
            "寒武纪",
            max_investors=20,
        )
        serialized = "\n".join(item["name"] for item in investors)
        self.assertNotIn("整体变更", serialized)
        self.assertNotIn("管理有限公司\n", serialized + "\n")

    def test_html_tags_are_removed_from_public_titles(self):
        self.assertEqual(
            parser.clean_text("首次公开发行<em>招股说明书</em>"),
            "首次公开发行招股说明书",
        )

    def test_unbalanced_legal_names_are_rejected(self):
        pages = self._pages() + [
            Page(
                95,
                """
                本次发行前 本次发行后 股东名称 持股数 占比
                8 测试投资中心（有限合伙 2,000,000 0.50 2,000,000 0.45
                """,
            )
        ]
        investors = parser.extract_institutional_investors(pages, "寒武纪", max_investors=20)
        self.assertFalse(any("测试投资中心" in item["name"] for item in investors))


if __name__ == "__main__":
    unittest.main()
