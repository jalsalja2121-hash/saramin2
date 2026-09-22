from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import uuid

import streamlit as st
from selenium.common.exceptions import WebDriverException

from hiring_poc.analysis import SAMPLE_JOB, analyze
from hiring_poc.automation import run_automation
from hiring_poc.documents import create_report, report_html
from hiring_poc.settings import read_settings


ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="채용 업무 PoC", page_icon=":material/work:", layout="wide")


def fingerprint(*values):
    return hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def backend_settings():
    try:
        return read_settings(st.secrets)
    except st.errors.StreamlitSecretNotFoundError:
        return read_settings({})


for key, value in {"session_id": uuid.uuid4().hex, "analysis": None, "analysis_sig": None,
                   "document_sig": None, "report_text": "", "automation_result": None,
                   "automation_sig": None, "submitted_sigs": [], "job_text": SAMPLE_JOB}.items():
    st.session_state.setdefault(key, value)

with st.sidebar:
    st.title("채용 업무 PoC")
    st.caption("Python · Streamlit · Selenium")
    settings = backend_settings()
    api_key = settings.api_key
    live = bool(api_key)
    mode = "실제 LLM · Gemini" if live else "데모 · API 키 없이 체험"
    model = settings.model if live else ""
    # Remove credentials left by older versions of the sidebar widget.
    st.session_state.pop("api_key", None)
    if live:
        st.caption("Gemini · 백엔드 키 설정됨")
        st.caption(f"모델: {model}")
        st.caption("분석 실행 시 입력한 공고가 Google Gemini로 전송됩니다. API 사용료가 발생할 수 있습니다.")
    else:
        st.info("백엔드 GEMINI_API_KEY가 아직 설정되지 않아 규칙 기반 데모로 실행 중입니다.")
    st.divider()
    st.markdown("**사용 순서**\n\n1. 공고 붙여넣기 → 분석\n2. 보고서 생성 → 수정·다운로드\n3. 사이트 입력 → 저장 확인")

st.title("채용 공고에서 업무 실행까지")
st.caption("세 가지 기능을 한 흐름으로 검증하는 Python PoC")
tabs = st.tabs(["1. 채용 공고 분석", "2. 문서 작성", "3. 업무 자동화"])

with tabs[0]:
    left, right = st.columns([1, 1], gap="large")
    with left:
        st.subheader("채용 공고 입력")
        st.caption("예시 공고는 가상 데이터입니다. 실제 공고로 교체할 수 있습니다.")
        text = st.text_area("공고 원문", height=400, max_chars=30000, key="job_text")
        current_sig = fingerprint(text.strip(), mode, model)
        if st.session_state.analysis_sig != current_sig:
            st.session_state.analysis = None
            st.session_state.document_sig = None
            st.session_state.automation_result = None
        if st.button("공고 분석", type="primary", icon=":material/search:", key="analyze"):
            try:
                with st.spinner("공고를 분석하고 있습니다..."):
                    result = analyze(text, "live" if live else "demo", api_key, model)
                st.session_state.analysis = result
                st.session_state.analysis_sig = current_sig
                st.session_state.document_sig = None
                st.session_state.automation_result = None
            except (ValueError, RuntimeError) as exc:
                st.error(str(exc))
    with right:
        st.subheader("분석 결과")
        job = st.session_state.analysis
        if job:
            st.caption(f"분석 방식: {'LLM · ' + model if live else '데모 · 규칙 기반'}")
            st.table({"항목": ["회사", "직무", "근무지", "고용형태", "경력", "마감일"],
                      "내용": [getattr(job, k) or "미기재" for k in
                               ["company", "role", "location", "employment_type", "experience", "deadline"]]})
            for title, items in [("주요 업무", job.responsibilities), ("필수 조건", job.required),
                                 ("우대 사항", job.preferred), ("전형 절차", job.process)]:
                with st.expander(f"{title} · {len(items)}개", expanded=title == "필수 조건"):
                    if items:
                        st.dataframe([{"항목": x.item, "원문 근거": x.evidence} for x in items], hide_index=True)
                    else:
                        st.caption("공고에서 확인하지 못했습니다.")
            if job.missing_information:
                st.warning("추가 확인: " + ", ".join(job.missing_information))
            st.download_button("분석 JSON 다운로드", job.model_dump_json(indent=2), "analysis.json", "application/json")
        else:
            st.info("왼쪽에서 공고를 분석하면 조건과 원문 근거가 표시됩니다.")

with tabs[1]:
    st.subheader("분석 보고서 작성")
    st.caption("분석 결과를 문서로 구성합니다. 생성 후 본문을 직접 수정할 수 있습니다.")
    notes = st.text_area("작성자 메모 (선택)", placeholder="검토 의견이나 후속 확인 사항을 입력하세요.", key="notes")
    document_sig = fingerprint(current_sig, notes)
    if st.button("보고서 생성", type="primary", disabled=job is None, key="generate", icon=":material/description:"):
        st.session_state.report_text = create_report(job, "LLM · " + model if live else "데모 · 규칙 기반", notes)
        st.session_state.document_sig = document_sig
        st.session_state.automation_result = None
        st.session_state.doc_title = f"{job.company or '회사 미기재'} · {job.role or '직무 미기재'} 분석 보고서"
        st.session_state.insert_company = job.company or ""
        st.session_state.insert_role = job.role or ""
    document_ready = bool(job and st.session_state.document_sig == document_sig)
    if document_ready:
        title = st.text_input("문서 제목", key="doc_title")
        body = st.text_area("보고서 본문 · 직접 수정 가능", height=500, max_chars=100000, key="report_text")
        with st.container(horizontal=True):
            st.download_button("TXT 다운로드", body.encode("utf-8-sig"), "report.txt", "text/plain", key="download_txt")
            st.download_button("HTML 다운로드", report_html(title, body), "report.html", "text/html", key="download_html")
        st.caption("HTML 파일은 브라우저에서 열어 인쇄하거나 PDF로 저장할 수 있습니다.")
    else:
        st.info("공고 분석 후 보고서를 생성해 주세요. 공고·분석 모드·메모가 바뀌면 다시 생성해야 합니다.")
        title, body = "", ""

with tabs[2]:
    st.subheader("Selenium 사이트 입력")
    st.caption("작성한 문서를 브라우저 입력란에 채웁니다. 로컬 데모에서는 저장된 데이터까지 대조합니다.")
    target = st.selectbox("입력 대상", ["로컬 데모 사이트", "사용자 지정 사이트"], key="target")
    browser = st.selectbox("자동화 브라우저", ["chrome", "edge"], key="browser")
    custom = None
    config_valid = True
    if target == "사용자 지정 사이트":
        st.info("일반 input·textarea가 있는 페이지를 지원합니다. 로그인, CAPTCHA, iframe, 파일 첨부는 사이트별 추가 구현이 필요합니다.")
        with st.expander("사이트 주소와 입력란 설정", expanded=True):
            config_text = st.text_area("사이트 설정 (JSON)", value=json.dumps({
                "url": "https://example.com/form",
                "fields": {"company": "#company", "role": "#role", "title": "#title", "body": "#body"},
                "submit": "#submit", "success": "#success"
            }, indent=2), height=280, key="site_config")
            try:
                custom = json.loads(config_text)
                if not isinstance(custom, dict) or not custom:
                    raise ValueError("JSON 객체가 필요합니다.")
            except (ValueError, TypeError):
                config_valid = False
                st.error("사이트 설정을 올바른 JSON 객체로 입력해 주세요.")
    if document_ready:
        a, b = st.columns(2)
        company = a.text_input("사이트에 입력할 회사", key="insert_company")
        role = b.text_input("사이트에 입력할 직무", key="insert_role")
        payload = {"company": company.strip(), "role": role.strip(), "title": title.strip(), "body": body.strip()}
        action = st.selectbox("실행 범위", ["입력만 확인", "입력 후 저장"], key="action")
        submit = action == "입력 후 저장"
        if custom and submit:
            st.caption("실행하면 지정한 외부 사이트의 저장 버튼을 누릅니다. 실패 시에도 저장됐을 수 있으므로 사이트에서 확인 후 재실행하세요.")
        auto_sig = fingerprint(payload, target, custom, submit, browser)
        already_submitted = auto_sig in st.session_state.submitted_sigs
        if already_submitted:
            st.info("이 세션에서 같은 내용의 저장을 완료했습니다.")
        if st.button("자동화 실행", type="primary", key="automate",
                     disabled=not config_valid or already_submitted or not all(payload.values()), icon=":material/play_arrow:"):
            st.session_state.automation_result = None
            try:
                with st.spinner("브라우저 입력과 실행 결과를 확인하고 있습니다..."):
                    output = run_automation(payload, run_id=fingerprint(st.session_state.session_id, payload),
                                            db=ROOT / "outputs" / "submissions.sqlite3", browser=browser,
                                            submit=submit, custom=custom)
                st.session_state.automation_result = output
                st.session_state.automation_sig = auto_sig
                if submit:
                    st.session_state.submitted_sigs.append(auto_sig)
                st.rerun()
            except WebDriverException:
                st.error("브라우저 실행·입력·완료 확인에 실패했습니다. 브라우저/드라이버 설치, 네트워크, 입력란 선택자를 확인해 주세요. 저장 실행이었다면 재시도 전에 사이트의 저장 여부를 확인하세요.")
            except (ValueError, RuntimeError, OSError) as exc:
                st.error(str(exc))
        output = st.session_state.automation_result
        if output and st.session_state.automation_sig == auto_sig:
            st.success(output.message)
            if output.record:
                with st.expander("저장 데이터 확인", expanded=True):
                    st.json(output.record)
                st.download_button("저장 결과 다운로드", json.dumps(output.record, ensure_ascii=False, indent=2), "submission.json", "application/json")
            if output.screenshot:
                st.image(output.screenshot, caption="Selenium 실행 결과")
    else:
        st.info("문서 작성 탭에서 보고서를 먼저 생성해 주세요.")

st.divider()
st.caption("로컬 PoC · 분석과 문서는 현재 브라우저 세션에 보관됩니다. 데모 사이트의 저장 결과는 outputs/submissions.sqlite3에 남습니다.")
