import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from hiring_poc.analysis import SAMPLE_JOB, analyze, demo_analysis
from hiring_poc.documents import create_report, report_html
from hiring_poc.automation import run_automation
from hiring_poc.demo_site import demo_server, get_submission

ROOT = Path(__file__).resolve().parents[1]


def test_analysis_report_and_escaping():
    job = demo_analysis(SAMPLE_JOB)
    assert job.company == "넥스트워크 (가상 기업)"
    assert len(job.required) == 3
    assert len(job.preferred) == 3
    assert all(x.evidence in SAMPLE_JOB for x in job.required + job.preferred)
    assert "급여 조건" in job.missing_information
    assert "Selenium" in create_report(job, "데모")
    html = report_html("<script>bad</script>", "<img src=x onerror=bad>").decode()
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html


def test_invalid_and_unstructured_sources():
    with pytest.raises(ValueError):
        demo_analysis("짧은 공고")
    job = demo_analysis("아무런 회사나 직무 정보가 없는 텍스트입니다. 필요한 정보를 추측해서는 안 됩니다.")
    assert job.company is None and not job.required
    with pytest.raises(ValueError):
        analyze(SAMPLE_JOB, "live", "", "model")


def test_live_contract_and_invalid_evidence(monkeypatch):
    import openai
    result = demo_analysis(SAMPLE_JOB)
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_parsed=result)

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    assert analyze(SAMPLE_JOB, "live", "test-key", "test-model") == result
    assert captured["store"] is False
    assert captured["model"] == "test-model"
    result.required[0].evidence = "원문에 없는 가짜 인용"
    with pytest.raises(ValueError, match="근거"):
        analyze(SAMPLE_JOB, "live", "test-key", "test-model")


def test_streamlit_flow_and_stale_results():
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20).run()
    assert not at.exception
    assert at.button(key="generate").disabled
    at.button(key="analyze").click().run()
    assert not at.exception
    at.button(key="generate").click().run()
    assert not at.exception
    assert "분석 보고서" in at.text_area(key="report_text").value
    at.text_area(key="report_text").set_value("직접 수정한 보고서").run()
    assert at.text_area(key="report_text").value == "직접 수정한 보고서"
    at.text_area(key="notes").set_value("메모 변경").run()
    assert not any(x.key == "automate" for x in at.button)
    at.button(key="generate").click().run()
    at.text_area(key="job_text").set_value(SAMPLE_JOB.replace("넥스트워크", "새 회사")).run()
    assert at.session_state["analysis"] is None
    assert at.button(key="generate").disabled
    assert not at.exception


def test_backend_key_auto_connects(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20)
    at.secrets["OPENAI_API_KEY"] = "test-backend-key"
    at.run()
    assert not at.exception
    assert any("백엔드 키 설정됨" in item.value for item in at.caption)
    assert not any(item.key == "api_key" for item in at.text_input)
    assert all("test-backend-key" not in item.value for item in at.caption)


def test_demo_http_insert_idempotent(tmp_path):
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
    db = tmp_path / "demo.sqlite3"
    with demo_server(db, "one-run") as url:
        token = url.rsplit("/", 1)[-1]
        payload = dict(company="회사", role="개발자", title="보고서", body="내용", token=token)
        for _ in range(2):
            request = Request(url, data=urlencode(payload).encode(), method="POST")
            with urlopen(request, timeout=3) as response:
                assert response.status == 200
        assert get_submission(db, "one-run")["company"] == "회사"
        import sqlite3
        with sqlite3.connect(db) as con:
            assert con.execute("SELECT count(*) FROM submissions").fetchone()[0] == 1


@pytest.mark.browser
def test_real_selenium_insert(tmp_path):
    import os
    if os.environ.get("RUN_BROWSER_TESTS") != "1":
        pytest.skip("Set RUN_BROWSER_TESTS=1 to run the real browser test")
    payload = dict(company="검증 회사", role="Python 개발자", title="자동화 검증", body="첫 번째 줄\n두 번째 줄 & <문자>")
    db = tmp_path / "submissions.sqlite3"
    result = run_automation(payload, run_id="real-browser", db=db, submit=False)
    assert result.status == "filled" and result.screenshot
    assert get_submission(db, "real-browser") is None
    result = run_automation(payload, run_id="real-browser", db=db, submit=True)
    assert result.status == "saved"
    assert all(result.record[k] == v for k, v in payload.items())
    duplicate = run_automation(payload, run_id="real-browser", db=db, submit=True)
    assert duplicate.status == "saved" and not duplicate.screenshot
