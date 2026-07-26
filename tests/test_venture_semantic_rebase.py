from __future__ import annotations

import unittest

from tools import enforce_venture_entity_semantics as semantics
from tools import finalize_venture_profiles as finalizer
from tools import refine_venture_research_evidence as refiner


class VentureSemanticRebaseTests(unittest.TestCase):
    def test_rejects_bare_generic_product_names(self) -> None:
        self.assertFalse(semantics._valid_product("API"))
        self.assertFalse(semantics._valid_product("Platform"))
        self.assertTrue(semantics._valid_product("企业 API"))
        self.assertTrue(semantics._valid_product("Claude Platform"))

    def test_accepts_official_short_brand_financing_subject(self) -> None:
        row = {
            "title": "SambaNova Completes First Close of $1B Financing",
            "summary": "SambaNova completed the financing at an $11B valuation.",
            "sourceUrl": "https://sambanova.ai/news/financing",
        }
        self.assertTrue(
            semantics._subject_evidence(
                row,
                ("SambaNova Systems", "SambaNova"),
                "sambanova.ai",
                semantics.FINANCING_ACTION_RE,
            )
        )

    def test_rejects_earnings_guidance_and_time_series_as_financing(self) -> None:
        earnings = (
            "IonQ Posts Q1 Earnings. The company raised full year guidance."
        )
        insar = (
            "IonQ launches automated 3-day repeat InSAR time series data."
        )
        self.assertIsNone(refiner.FINANCING_RE.search(earnings))
        self.assertIsNone(refiner.FINANCING_RE.search(insar))
        self.assertIsNone(refiner.ROUND_RE.search(insar))
        self.assertIsNone(semantics.FINANCING_ACTION_RE.search(earnings))
        self.assertIsNone(semantics.FINANCING_ACTION_RE.search(insar))
        self.assertEqual(
            finalizer.finalize_financing([
                {
                    "date": "2026-06-10",
                    "type": "融资",
                    "title": "IonQ Posts Q1 2026 Earnings with Record Revenue",
                    "summary": "IonQ raised full year guidance after record revenue.",
                    "round": "Growth",
                    "sourceUrl": "https://ionq.com/news/results",
                }
            ]),
            [],
        )


if __name__ == "__main__":
    unittest.main()
