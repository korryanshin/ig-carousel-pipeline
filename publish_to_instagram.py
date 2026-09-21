#!/usr/bin/env python3
"""
4단계: check_selection.py 가 만든 이미지가 git push 되어 raw.githubusercontent.com
       으로 접근 가능해진 뒤에 실행 -> Instagram 캐러셀 업로드 담당.

워크플로우 순서 (.github/workflows/check_and_publish.yml 참고):
  1) check_selection.py 실행 (이미지 생성, image_urls.json 기록)
  2) git add/commit/push (이미지 파일들을 저장소에 반영)
  3) publish_to_instagram.py 실행 (raw URL로 IG 업로드)

필요한 환경변수:
  IG_ACCESS_TOKEN, IG_BUSINESS_ACCOUNT_ID, GITHUB_REPOSITORY, GITHUB_REF_NAME
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (완료 알림용)
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"

IG_TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_ACCOUNT_ID = os.environ.get("IG_BUSINESS_ACCOUNT_ID")
GH_REPO = os.environ.get("GITHUB_REPOSITORY")
GH_BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

GRAPH_API = "https://graph.facebook.com/v21.0"
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}" if BOT_TOKEN else None


def raw_url(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return f"https://raw.githubusercontent.com/{GH_REPO}/{GH_BRANCH}/{rel}"


def find_pending_run() -> Path | None:
    """image_urls.json 이 있고 아직 published.json 이 없는 가장 최근 디렉터리를 찾음."""
    if not OUTPUT_DIR.exists():
        return None
    candidates = []
    for d in OUTPUT_DIR.iterdir():
        if not d.is_dir():
            continue
        if (d / "image_urls.json").exists() and not (d / "published.json").exists():
            candidates.append(d)
    if not candidates:
        return None
    return sorted(candidates)[-1]


def ig_create_item(image_url: str) -> str:
    resp = requests.post(
        f"{GRAPH_API}/{IG_ACCOUNT_ID}/media",
        data={"image_url": image_url, "is_carousel_item": "true", "access_token": IG_TOKEN},
        timeout=30,
    )
    data = resp.json()
    if "id" not in data:
        raise RuntimeError(f"IG 컨테이너 생성 실패: {data}")
    return data["id"]


def ig_create_carousel(children_ids: list, caption: str) -> str:
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


def notify(text: str):
    if not TG_API or not CHAT_ID:
        return
    try:
        requests.post(f"{TG_API}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(f"[경고] 텔레그램 알림 실패: {e}")


def main():
    missing = [n for n, v in [("IG_ACCESS_TOKEN", IG_TOKEN), ("IG_BUSINESS_ACCOUNT_ID", IG_ACCOUNT_ID), ("GITHUB_REPOSITORY", GH_REPO)] if not v]
    if missing:
        print(f"[오류] 다음 환경변수가 필요합니다: {', '.join(missing)}")
        sys.exit(1)

    run_dir = find_pending_run()
    if not run_dir:
        print("업로드 대기 중인 게시물이 없습니다. 종료.")
        return

    info = json.loads((run_dir / "image_urls.json").read_text(encoding="utf-8"))
    image_paths = [Path(p) for p in info["images"]]
    caption = info.get("caption", info.get("title", ""))

    print(f"'{info.get('title')}' 업로드 시작 ({len(image_paths)}장)")

    child_ids = []
    for p in image_paths:
        url = raw_url(p)
        print(f"  - 컨테이너 생성: {url}")
        child_ids.append(ig_create_item(url))
        time.sleep(1)  # Graph API rate limit 여유

    carousel_id = ig_create_carousel(child_ids, caption)
    time.sleep(2)  # 컨테이너 처리 대기
    media_id = ig_publish(carousel_id)

    (run_dir / "published.json").write_text(
        json.dumps({"media_id": media_id, "published_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"게시 완료! media_id={media_id}")
    notify(f"✅ 인스타그램에 업로드 완료!\n제목: {info.get('title')}")


if __name__ == "__main__":
    main()
