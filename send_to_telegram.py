#!/usr/bin/env python3
"""
2단계: topics.json 의 상위 주제를 텔레그램으로 전송 (인라인 버튼 포함)

필요한 환경변수:
  TELEGRAM_BOT_TOKEN  - BotFather에서 발급받은 토큰
  TELEGRAM_CHAT_ID    - 메시지를 받을 본인의 chat id

사용법:
  python3 send_to_telegram.py
"""

import json
import os
import sys
from pathlib import Path

import requests

TOPICS_FILE = Path(__file__).parent / "topics.json"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def main():
    if not BOT_TOKEN or not CHAT_ID:
        print("[오류] TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수가 필요합니다.")
        sys.exit(1)

    if not TOPICS_FILE.exists():
        print(f"[오류] {TOPICS_FILE} 가 없습니다. 먼저 collect_topics.py 를 실행하세요.")
        sys.exit(1)

    data = json.loads(TOPICS_FILE.read_text(encoding="utf-8"))
    topics = data.get("topics", [])
    if not topics:
        print("수집된 주제가 없어 발송을 건너뜁니다.")
        return

    lines = ["📋 *오늘의 캐러셀 후보 주제*\n"]
    keyboard_rows = []
    for i, t in enumerate(topics):
        lines.append(f"{i + 1}. {t['title']}")
        keyboard_rows.append([
            {"text": f"{i + 1}번 선택", "callback_data": f"pick:{i}"}
        ])
    lines.append("\n아래 버튼을 눌러 게시물로 만들 주제를 선택하세요.")

    text = "\n".join(lines)

    resp = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": keyboard_rows},
        },
        timeout=15,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        print(f"[오류] 텔레그램 발송 실패: {result}")
        sys.exit(1)

    print(f"텔레그램 발송 완료. {len(topics)}개 주제 전송됨.")


if __name__ == "__main__":
    main()
