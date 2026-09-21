#!/usr/bin/env python3
"""
3단계: 텔레그램에서 사용자의 버튼 선택을 확인하고,
       선택되었으면 캐러셀 이미지를 생성해 인스타그램에 업로드한다.

이 스크립트는 GitHub Actions에서 짧은 주기(예: 15분)로 반복 실행되도록 설계되어
있습니다. 매번:
  1) 텔레그램 getUpdates 로 새 콜백이 있는지 확인 (offset은 state/ 에 저장해 중복 방지)
  2) 콜백이 있으면 topics.json 에서 해당 주제를 찾음
  3) generate_carousel.py 로 카드 이미지 생성 (output/<slug>/*.png)
  4) 이미지가 GitHub raw URL로 접근 가능해지도록 커밋 (워크플로우 쪽에서 git push 수행)
  5) Instagram Graph API 로 캐러셀 업로드
  6) 완료 메시지를 텔레그램으로 회신

필요한 환경변수:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
  IG_ACCESS_TOKEN            - Instagram Graph API 장기 액세스 토큰
  IG_BUSINESS_ACCOUNT_ID     - Instagram 비즈니스 계정 ID
  GITHUB_REPOSITORY          - "owner/repo" (GitHub Actions에서 자동 제공)
  GITHUB_REF_NAME            - 브랜치명 (GitHub Actions에서 자동 제공, 보통 "main")

종료 코드:
  0 = 정상 (선택 없었거나, 선택 처리 후 업로드까지 완료)
  1 = 오류
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

from generate_carousel import build_carousel

ROOT = Path(__file__).parent
TOPICS_FILE = ROOT / "topics.json"
STATE_FILE = ROOT / "state" / "last_update_id.json"
OUTPUT_DIR = ROOT / "output"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
IG_TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
GH_REPO = os.environ.get("GITHUB_REPOSITORY")  # 예: "your-name/ig-carousel-pipeline"
GH_BRANCH = os.environ.get("GITHUB_REF_NAME", "main")

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
GRAPH_API = "https://graph.facebook.com/v21.0"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"last_update_id": 0}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_latest_callback() -> tuple[dict | None, int]:
    """가장 최근 콜백 쿼리 1건과, 처리 완료 후 저장할 새 offset을 반환."""
    state = load_state()
    offset = state.get("last_update_id", 0) + 1

    resp = requests.get(f"{TG_API}/getUpdates", params={"offset": offset, "timeout": 0}, timeout=15)
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"getUpdates 실패: {result}")

    updates = result.get("result", [])
    if not updates:
        return None, state.get("last_update_id", 0)

    new_last_id = max(u["update_id"] for u in updates)

    callback_updates = [u for u in updates if "callback_query" in u]
    if not callback_updates:
        return None, new_last_id

    # 가장 마지막 콜백만 사용 (여러 번 눌렀으면 최신 선택 우선)
    latest = callback_updates[-1]
    return latest["callback_query"], new_last_id


def answer_callback(callback_query_id: str, text: str):
    requests.post(
        f"{TG_API}/answerCallbackQuery",
        json={"callback_query_id": callback_query_id, "text": text},
        timeout=10,
    )


def send_message(text: str):
    requests.post(
        f"{TG_API}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=10,
    )


def slugify(text: str) -> str:
    keep = [c if c.isalnum() else "-" for c in text]
    slug = "".join(keep).strip("-")
    return (slug[:40] or "topic").lower()


def raw_url(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{GH_REPO}/{GH_BRANCH}/{rel}"


def ig_create_item(image_url: str, is_carousel_item=True) -> str:
    resp = requests.post(
        f"{GRAPH_API}/{IG_ACCOUNT_ID}/media",
        data={
            "image_url": image_url,
            "is_carousel_item": "true" if is_carousel_item else "false",
            "access_token": IG_TOKEN,
        },
        timeout=30,
    )
    data = resp.json()
    if "id" not in data:
        raise RuntimeError(f"IG 컨테이너 생성 실패: {data}")
    return data["id"]


def ig_create_carousel(children_ids: list[str], caption: str) -> str:
    resp = requests.post(
        f"{GRAPH_API}/{IG_ACCOUNT_ID}/media",
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(children_ids),
            "caption": caption,
            "access_token": IG_TOKEN,
        },
        timeout=30,
    )
    data = resp.json()
    if "id" not in data:
        raise RuntimeError(f"IG 캐러셀 컨테이너 생성 실패: {data}")
    return data["id"]


def ig_publish(container_id: str) -> str:
    resp = requests.post(
        f"{GRAPH_API}/{IG_ACCOUNT_ID}/media_publish",
        data={"creation_id": container_id, "access_token": IG_TOKEN},
        timeout=30,
    )
    data = resp.json()
    if "id" not in data:
        raise RuntimeError(f"IG 게시 실패: {data}")
    return data["id"]


def main():
    missing = [
        name for name, val in [
            ("TELEGRAM_BOT_TOKEN", BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", CHAT_ID),
            ("IG_ACCESS_TOKEN", IG_TOKEN),
            ("IG_BUSINESS_ACCOUNT_ID", IG_ACCOUNT_ID),
            ("GITHUB_REPOSITORY", GH_REPO),
        ] if not val
    ]
    if missing:
        print(f"[오류] 다음 환경변수가 필요합니다: {', '.join(missing)}")
        sys.exit(1)

    callback, new_last_id = get_latest_callback()
    save_state({"last_update_id": new_last_id})

    if not callback:
        print("새 선택 없음. 종료.")
        return

    data = callback.get("data", "")
    if not data.startswith("pick:"):
        print(f"알 수 없는 콜백 데이터: {data}")
        return

    idx = int(data.split(":")[1])
    topics_data = json.loads(TOPICS_FILE.read_text(encoding="utf-8"))
    topics = topics_data.get("topics", [])
    if idx >= len(topics):
        answer_callback(callback["id"], "이미 만료된 선택입니다. 새 목록을 기다려주세요.")
        return

    topic = topics[idx]
    title = topic["title"]
    print(f"선택된 주제: {title}")
    answer_callback(callback["id"], f"'{title}' 선택됨! 게시물 생성 중...")
    send_message(f"🎨 '{title}' 주제로 캐러셀을 만들고 있어요...")

    # ── 콘텐츠 생성 ──────────────────────────────
    # TODO: 여기서 실제로는 주제에 맞는 슬라이드 문구(불릿)를 만들어야 합니다.
    #       지금은 원문 제목/링크 기반의 간단한 플레이스홀더를 사용합니다.
    #       Claude API 등으로 본문을 자동 생성하도록 이 부분을 교체하세요.
    bullets = [
        f"원문: {title}",
        f"출처: {topic.get('source', '알 수 없음')}",
        "자세한 내용은 프로필 링크를 확인하세요.",
    ]

    slug = f"{time.strftime('%Y%m%d-%H%M%S')}-{slugify(title)}"
    out_dir = OUTPUT_DIR / slug
    image_paths = build_carousel(title, bullets, out_dir)
    print(f"{len(image_paths)}장 이미지 생성 완료: {out_dir}")

    # 이 시점에서 워크플로우(.yml)가 이 커밋을 git add/commit/push 해서
    # raw.githubusercontent.com 으로 접근 가능하게 만들어야 합니다.
    # 여기서는 push가 이미 끝났다고 가정하고 진행할 수 없으므로,
    # 워크플로우는 이 스크립트 실행 -> git commit/push -> 아래 업로드 단계를
    # 순서대로 분리 실행합니다. (README 참고)
    urls_file = out_dir / "image_urls.json"
    urls_file.write_text(
        json.dumps({"title": title, "caption": title, "images": [str(p) for p in image_paths]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"업로드 대기 정보 저장: {urls_file}")


if __name__ == "__main__":
    main()
