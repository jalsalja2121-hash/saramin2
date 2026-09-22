from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .demo_site import demo_server, get_submission


@dataclass
class AutomationResult:
    status: str
    message: str
    screenshot: bytes
    record: dict | None = None


@contextmanager
def browser_session(browser: str = "chrome"):
    if browser not in {"chrome", "edge"}:
        raise ValueError("Chrome 또는 Edge를 선택해 주세요.")
    options = webdriver.ChromeOptions() if browser == "chrome" else webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1100")
    options.add_argument("--disable-background-networking")
    binary = os.environ.get("BROWSER_BINARY")
    if binary:
        options.binary_location = binary
    # Optional explicit driver supports offline/managed environments.
    path = os.environ.get("WEBDRIVER_PATH")
    service_cls = ChromeService if browser == "chrome" else EdgeService
    service = service_cls(executable_path=path) if path else service_cls()
    driver_cls = webdriver.Chrome if browser == "chrome" else webdriver.Edge
    driver = driver_cls(options=options, service=service)
    try:
        driver.set_page_load_timeout(30)
        yield driver
    finally:
        driver.quit()


def fill(driver, payload: dict[str, str], selectors: dict[str, str]):
    wait = WebDriverWait(driver, 15)
    for key, value in payload.items():
        element = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selectors[key])))
        element.clear()
        element.send_keys(value)
        actual = element.get_attribute("value") or ""
        if actual.replace("\r\n", "\n") != value.replace("\r\n", "\n"):
            raise RuntimeError(f"{key} 입력값이 일치하지 않습니다. 필드 형식을 확인해 주세요.")


def run_automation(payload: dict[str, str], *, run_id: str, db: Path, browser: str = "chrome",
                   submit: bool = False, custom: dict | None = None) -> AutomationResult:
    keys = {"company", "role", "title", "body"}
    if set(payload) != keys or any(not isinstance(v, str) or not v.strip() for v in payload.values()):
        raise ValueError("회사, 직무, 문서 제목과 본문을 모두 입력해 주세요.")
    if any(len(v) > 100000 for v in payload.values()):
        raise ValueError("각 입력 항목은 100,000자 이하로 작성해 주세요.")
    payload = {k: v.replace("\r\n", "\n").strip() for k, v in payload.items()}
    if custom:
        url = custom.get("url", "")
        if not isinstance(url, str):
            raise ValueError("사이트 주소는 문자열이어야 합니다.")
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("로그인 정보가 포함되지 않은 http/https 주소를 입력해 주세요.")
        selectors = custom.get("fields", {})
        if not isinstance(selectors, dict) or set(selectors) != keys or not all(isinstance(v, str) and v.strip() for v in selectors.values()):
            raise ValueError("fields에는 company, role, title, body의 CSS 선택자가 필요합니다.")
        if submit and not all(isinstance(custom.get(k), str) and custom[k].strip() for k in ("submit", "success")):
            raise ValueError("저장 시 submit과 success 선택자가 모두 필요합니다.")
        with browser_session(browser) as driver:
            driver.get(url)
            fill(driver, payload, selectors)
            if submit:
                # Existing success messages must not be mistaken for this submission's result.
                if any(e.is_displayed() for e in driver.find_elements(By.CSS_SELECTOR, custom["success"])):
                    raise ValueError("저장 전부터 성공 표시가 있습니다. 새 저장 완료 상태만 가리키는 선택자를 지정해 주세요.")
                WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.CSS_SELECTOR, custom["submit"]))).click()
                WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, custom["success"])))
            return AutomationResult("submitted" if submit else "filled",
                                    "사이트의 저장 완료 표시를 확인했습니다." if submit else "입력값을 확인했습니다. 저장 버튼은 누르지 않았습니다.",
                                    driver.get_screenshot_as_png())
    # Same run ID is idempotent even across UI reruns or process restarts.
    with demo_server(db, run_id) as url:
        existing = get_submission(db, run_id)
        if submit and existing:
            if any(existing[k] != v.strip() for k, v in payload.items()):
                raise ValueError("같은 실행 ID에 다른 내용이 이미 저장되어 있습니다.")
            return AutomationResult("saved", "동일한 실행이 이미 저장되어 중복 등록하지 않았습니다.", b"", existing)
        with browser_session(browser) as driver:
            driver.get(url)
            fill(driver, payload, {key: f"#{key}" for key in keys})
            if submit:
                driver.find_element(By.ID, "submit").click()
                WebDriverWait(driver, 15).until(EC.visibility_of_element_located((By.ID, "success")))
                record = get_submission(db, run_id)
                if not record or any(record[k] != v.strip() for k, v in payload.items()):
                    raise RuntimeError("저장된 데이터와 입력값이 일치하지 않습니다.")
                return AutomationResult("saved", "사이트 입력과 SQLite 저장 데이터 일치를 확인했습니다.", driver.get_screenshot_as_png(), record)
            return AutomationResult("filled", "입력값을 확인했습니다. 저장 버튼은 누르지 않았습니다.", driver.get_screenshot_as_png())
