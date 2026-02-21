from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from gemini_client import GeminiClientError, ask_gemini, validate_api_key
from prompts import CARD_ACTION_PROMPTS, HELPER_BUTTON_PROMPTS

st.set_page_config(page_title="쉬운 학습 도우미", page_icon="📘", layout="wide")


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "GEMINI_API_KEY": "",
        "api_status": "미확인",
        "history": [],
        "last_answer": "",
        "remember_key": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



def _load_cards() -> list[dict[str, str]]:
    cards_path = Path("data/sample_cards.json")
    with cards_path.open("r", encoding="utf-8") as file:
        return json.load(file)



def _summary_and_detail(text: str) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return text, ""
    summary = "\n".join(lines[:6])
    detail = "\n".join(lines[6:])
    return summary, detail



def _display_ai_answer(answer: str) -> None:
    summary, detail = _summary_and_detail(answer)
    st.markdown("### AI 답변(요약)")
    st.write(summary)
    if detail:
        with st.expander("자세히 보기"):
            st.write(detail)



def _key_input_area() -> None:
    st.subheader("시작/설정")
    st.info("개인정보(전화번호, 주소, 주민번호 등)는 입력하지 마세요.")

    key_input = st.text_input("Gemini API Key", type="password", value=st.session_state["GEMINI_API_KEY"])
    st.session_state["GEMINI_API_KEY"] = key_input.strip()

    st.session_state["remember_key"] = st.checkbox(
        "이 브라우저에서만 기억(선택)",
        value=st.session_state["remember_key"],
        help="기본값은 OFF이며, 켜면 현재 브라우저 세션에서만 유지됩니다.",
    )

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("연결 확인", use_container_width=True, type="primary"):
            if not st.session_state["GEMINI_API_KEY"]:
                st.session_state["api_status"] = "API 키 미입력"
            else:
                ok, message = validate_api_key(st.session_state["GEMINI_API_KEY"])
                st.session_state["api_status"] = message if ok else f"오류: {message}"

    with col2:
        status = st.session_state["api_status"]
        if status == "연결됨":
            st.success(f"상태: {status}")
        elif status.startswith("오류") or status == "API 키 미입력":
            st.warning(f"상태: {status}")
        else:
            st.info(f"상태: {status}")



def _learning_helper_tab() -> None:
    st.subheader("학습 도우미")
    st.caption("짧게 질문해도 괜찮아요. AI가 쉬운 말로 설명해 줄게요.")

    question = st.text_area("질문 입력", height=120, placeholder="예: 분수 더하기를 쉽게 설명해줘")
    has_key = bool(st.session_state["GEMINI_API_KEY"])

    ask_clicked = st.button("AI에게 물어보기", use_container_width=True, type="primary", disabled=not has_key)
    if not has_key:
        st.warning("먼저 시작/설정 화면에서 API 키를 입력해 주세요.")

    if ask_clicked and question.strip():
        with st.spinner("생각 중이에요..."):
            try:
                answer = ask_gemini(st.session_state["GEMINI_API_KEY"], question.strip())
                st.session_state["last_answer"] = answer
                st.session_state["history"].append({"q": question.strip(), "a": answer})
            except GeminiClientError as exc:
                st.error(str(exc))
                st.exception(exc)

    if st.session_state["last_answer"]:
        _display_ai_answer(st.session_state["last_answer"])

        st.markdown("### 답변 다듬기")
        cols = st.columns(4)
        for idx, (label, prompt) in enumerate(HELPER_BUTTON_PROMPTS.items()):
            with cols[idx]:
                if st.button(label, use_container_width=True, disabled=not has_key):
                    with st.spinner("다시 정리 중이에요..."):
                        try:
                            rewritten = ask_gemini(
                                st.session_state["GEMINI_API_KEY"],
                                prompt,
                                extra_context=st.session_state["last_answer"],
                            )
                            st.session_state["last_answer"] = rewritten
                            st.session_state["history"].append({"q": label, "a": rewritten})
                        except GeminiClientError as exc:
                            st.error(str(exc))
                            st.exception(exc)

    with st.expander("대화 기록"):
        if st.button("대화 지우기"):
            st.session_state["history"] = []
            st.session_state["last_answer"] = ""
            st.success("대화 기록을 지웠어요.")

        if not st.session_state["history"]:
            st.write("아직 대화 기록이 없어요.")
        else:
            for i, item in enumerate(reversed(st.session_state["history"]), start=1):
                st.markdown(f"**{i}. 질문/요청:** {item['q']}")
                st.write(item["a"])



def _today_learning_tab() -> None:
    st.subheader("오늘의 학습/복습")
    st.caption("짧은 학습 카드로 연습해요. API 키가 없어도 카드는 볼 수 있어요.")

    cards = _load_cards()
    options = [f"{idx+1}. {card['title']}" for idx, card in enumerate(cards)]
    selected = st.selectbox("카드 선택", options=options)
    card_index = options.index(selected)
    card = cards[card_index]

    st.markdown(f"### {card['title']}")
    st.write(card["content"])

    if card.get("hint"):
        st.info(f"힌트: {card['hint']}")

    has_key = bool(st.session_state["GEMINI_API_KEY"])
    action_cols = st.columns(3)

    for idx, (label, prompt) in enumerate(CARD_ACTION_PROMPTS.items()):
        with action_cols[idx]:
            if st.button(label, use_container_width=True, disabled=not has_key):
                with st.spinner("학습 카드 설명을 준비 중이에요..."):
                    try:
                        result = ask_gemini(
                            st.session_state["GEMINI_API_KEY"],
                            prompt,
                            extra_context=f"제목: {card['title']}\n내용: {card['content']}",
                        )
                        _display_ai_answer(result)
                    except GeminiClientError as exc:
                        st.error(str(exc))
                        st.exception(exc)

    if not has_key:
        st.warning("API 키가 없어서 AI 확장 기능은 잠겨 있어요. 카드 학습은 계속할 수 있어요.")



def main() -> None:
    _init_state()
    st.title("📘 쉬운 학습 도우미")
    st.write("한 번에 한 단계씩, 짧고 쉽게 함께 배워요.")

    tab_start, tab_helper, tab_today = st.tabs(["시작/설정", "학습 도우미", "오늘의 학습/복습"])

    with tab_start:
        _key_input_area()
    with tab_helper:
        _learning_helper_tab()
    with tab_today:
        _today_learning_tab()


if __name__ == "__main__":
    main()
