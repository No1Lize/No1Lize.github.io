from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from tools import research_agent_runtime as runtime


class ResearchAgentRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        runtime._LAST_FAILURE = None

    def test_runtime_policy_overrides_timeout_and_retries(self) -> None:
        captured: dict[str, object] = {}

        def fake_call(**kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {"executiveSummary": "ok"}

        with mock.patch.object(
            runtime, "_ORIGINAL_CALL_SILICONFLOW", fake_call
        ), mock.patch.dict(
            os.environ,
            {
                "RESEARCH_AGENT_API_TIMEOUT": "180",
                "RESEARCH_AGENT_API_RETRIES": "1",
            },
            clear=False,
        ):
            result = runtime.call_siliconflow(
                api_key="secret-not-logged",
                base_url="https://api.example.test/v1",
                model="test-model",
                reasoning_effort="high",
                prompt="{}",
                timeout=1,
                retries=9,
            )

        self.assertEqual(result["executiveSummary"], "ok")
        self.assertEqual(captured["timeout"], 180.0)
        self.assertEqual(captured["retries"], 1)

    def test_timeout_is_classified_without_exposing_credentials(self) -> None:
        def fake_call(**_: object) -> dict[str, object]:
            raise RuntimeError("provider request failed") from TimeoutError("timed out")

        with mock.patch.object(
            runtime, "_ORIGINAL_CALL_SILICONFLOW", fake_call
        ), mock.patch.dict(
            os.environ,
            {
                "RESEARCH_AGENT_API_TIMEOUT": "30",
                "RESEARCH_AGENT_API_RETRIES": "0",
            },
            clear=False,
        ):
            with self.assertRaises(runtime.SiliconFlowTimeoutError) as caught:
                runtime.call_siliconflow(
                    api_key="secret-not-logged",
                    base_url="https://api.example.test/v1",
                    model="test-model",
                    reasoning_effort="high",
                    prompt="{}",
                )

        self.assertNotIn("secret-not-logged", str(caught.exception))
        self.assertIsNotNone(runtime._LAST_FAILURE)
        self.assertEqual(runtime._LAST_FAILURE["errorType"], "TimeoutError")

    def test_model_prompt_limits_changes_and_filters_unreferenced_evidence(self) -> None:
        captured: dict[str, object] = {}

        def fake_prompt(
            changes: list[dict[str, object]],
            evidence: list[dict[str, object]],
            as_of: str,
        ) -> str:
            captured["changes"] = changes
            captured["evidence"] = evidence
            captured["asOf"] = as_of
            return json.dumps({"ok": True})

        changes = [
            {"id": "c1", "evidenceIds": ["E001"]},
            {"id": "c2", "evidenceIds": ["E002"]},
            {"id": "c3", "evidenceIds": ["E003"]},
        ]
        evidence = [
            {"id": "E001"},
            {"id": "E002"},
            {"id": "E003"},
            {"id": "E999"},
        ]

        with mock.patch.object(
            runtime, "_ORIGINAL_MODEL_PROMPT", fake_prompt
        ), mock.patch.dict(
            os.environ,
            {"RESEARCH_AGENT_MODEL_CHANGE_LIMIT": "2"},
            clear=False,
        ):
            runtime.model_prompt(changes, evidence, "2026-08-07T00:00:00Z")

        self.assertEqual(
            [row["id"] for row in captured["changes"]], ["c1", "c2"]
        )
        self.assertEqual(
            [row["id"] for row in captured["evidence"]], ["E001", "E002"]
        )

    def test_generic_fallback_uses_sanitized_runtime_reason(self) -> None:
        runtime._LAST_FAILURE = {
            "publicReason": "SiliconFlow 模型请求超时，已切换到规则引擎"
        }

        def fake_fallback(
            _: list[dict[str, object]], reason: str
        ) -> dict[str, str]:
            return {"reason": reason}

        with mock.patch.object(
            runtime, "_ORIGINAL_FALLBACK_ANALYSIS", fake_fallback
        ):
            result = runtime.fallback_analysis([], "模型调用或结果校验失败")

        self.assertIn("请求超时", result["reason"])


if __name__ == "__main__":
    unittest.main()
