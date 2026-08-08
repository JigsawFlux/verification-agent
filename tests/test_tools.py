# tests/test_tools.py
import pytest
from unittest.mock import patch, MagicMock
from src.tools.adapter import ToolRegistry


def _mock_llm_response(content: str):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = content
    mock_llm.invoke.return_value = mock_response
    return mock_llm


class TestToolRegistry:
    def test_all_tools_registered(self):
        tools = ToolRegistry.available()
        assert "check_source_credibility" in tools
        assert "detect_manipulation_language" in tools
        assert "cross_check_claims" in tools
        assert "privacy_risk_check" in tools

    def test_unknown_tool_returns_error(self):
        result = ToolRegistry.run("nonexistent_tool", "some content")
        assert "error" in result
        assert result["tool"] == "nonexistent_tool"


class TestSourceCredibility:
    def test_returns_expected_schema(self):
        mock_json = '{"source_known": false, "author_identifiable": false, "domain_age_signal": "unknown", "credibility_score": 0.2, "risk_contribution": 0.8, "explanation": "No author found."}'
        with patch("src.tools.source_credibility.get_llm", return_value=_mock_llm_response(mock_json)):
            result = ToolRegistry.run("check_source_credibility", "test content")
        assert "source_known" in result
        assert "risk_contribution" in result
        assert "explanation" in result

    def test_json_parse_failure_returns_defaults(self):
        with patch("src.tools.source_credibility.get_llm", return_value=_mock_llm_response("INVALID JSON")):
            result = ToolRegistry.run("check_source_credibility", "test content")
        assert "risk_contribution" in result
        assert result["tool"] == "check_source_credibility"


class TestManipulationLanguage:
    def test_returns_expected_schema(self):
        mock_json = '{"urgency_present": true, "fear_language": true, "authority_pressure": false, "evidence_snippets": ["act now"], "risk_contribution": 0.9, "explanation": "Urgency language detected."}'
        with patch("src.tools.manipulation_language.get_llm", return_value=_mock_llm_response(mock_json)):
            result = ToolRegistry.run("detect_manipulation_language", "URGENT act now!")
        assert result["urgency_present"] is True
        assert "evidence_snippets" in result


class TestCrossCheck:
    def test_returns_expected_schema(self):
        mock_json = '{"claim_supported": false, "conflicting_sources": true, "date_context_ok": true, "evidence_quality": "weak", "consistency_score": 0.3, "risk_contribution": 0.7, "explanation": "Claims not supported."}'
        with patch("src.tools.cross_check.get_llm", return_value=_mock_llm_response(mock_json)):
            result = ToolRegistry.run("cross_check_claims", "Scientists cure all disease")
        assert "consistency_score" in result
        assert result["evidence_quality"] == "weak"


class TestPrivacyRisk:
    def test_returns_expected_schema(self):
        mock_json = '{"pii_solicitation": true, "payment_pressure": false, "credential_harvesting": false, "impersonation": true, "safety_warning_text": "Do not share your NI number.", "risk_contribution": 0.85, "explanation": "PII and impersonation detected."}'
        with patch("src.tools.privacy_risk.get_llm", return_value=_mock_llm_response(mock_json)):
            result = ToolRegistry.run("privacy_risk_check", "Enter your NI number")
        assert result["pii_solicitation"] is True
        assert result["impersonation"] is True
        assert "safety_warning_text" in result
