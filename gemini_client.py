from __future__ import annotations

import logging
from typing import Optional

from google import genai
from google.genai.types import GenerateContentConfig

from prompts import SYSTEM_PROMPT

MODEL_NAME = "gemini-3-flash-preview"
logger = logging.getLogger(__name__)


class GeminiClientError(Exception):
    """사용자에게 친절한 메시지로 변환할 수 있는 Gemini 호출 오류."""



def _to_user_friendly_error(exc: Exception) -> str:
    message = str(exc).lower()
    if "api" in message and "key" in message:
        return "API 키를 확인해 주세요. 키가 잘못되었거나 만료되었을 수 있어요."
    if "quota" in message or "429" in message:
        return "요청 한도에 도달했어요. 잠시 후 다시 시도해 주세요."
    if "network" in message or "connection" in message:
        return "네트워크 연결이 불안정해요. 인터넷 상태를 확인해 주세요."
    return "요청 처리 중 문제가 생겼어요. 잠시 후 다시 시도해 주세요."



def validate_api_key(api_key: str) -> tuple[bool, str]:
    """짧은 요청으로 API 키 연결 상태를 검사한다."""
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents="연결 확인이라고만 답해줘.",
            config=GenerateContentConfig(max_output_tokens=20),
        )
        text = (response.text or "").strip()
        if text:
            return True, "연결됨"
        return False, "응답이 비어 있어요. 다시 시도해 주세요."
    except Exception as exc:  # SDK 상세 예외 타입이 환경별로 다를 수 있어 범용 처리
        logger.exception("Gemini key validation failed")
        return False, _to_user_friendly_error(exc)



def ask_gemini(api_key: str, user_prompt: str, extra_context: Optional[str] = None) -> str:
    """학습자 친화형 시스템 프롬프트를 포함해 Gemini에 질의한다."""
    if not api_key:
        raise GeminiClientError("먼저 API 키를 입력해 주세요.")

    try:
        client = genai.Client(api_key=api_key)
        final_prompt = user_prompt
        if extra_context:
            final_prompt = f"{user_prompt}\n\n참고 자료:\n{extra_context}"

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=final_prompt,
            config=GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.5,
                max_output_tokens=300,
            ),
        )
        text = (response.text or "").strip()
        if not text:
            raise GeminiClientError("답변이 비어 있어요. 다시 질문해 주세요.")
        return text
    except GeminiClientError:
        raise
    except Exception as exc:
        logger.exception("Gemini request failed")
        raise GeminiClientError(_to_user_friendly_error(exc)) from exc
