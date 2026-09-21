#!/usr/bin/env python3
"""
1단계: 주제 수집 + 점수화
- 여러 RSS 피드에서 최신 기사를 모아온다
- 키워드 빈도 + 최신성으로 점수화
- 상위 N개를 topics.json 으로 저장 (텔레그램 발송 스크립트가 이 파일을 읽음)

사용법:
  python3 collect_topics.py

커스터마이징:
  - FEEDS 리스트에 원하는 RSS 주소를 추가/삭제하세요.
  - TOP_N 으로 몇 개를 뽑을지 조절하세요.
  - score_topic() 함수를 바꾸면 점수화 기준을 바꿀 수 있습니다.
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

# ── 설정 ────────────────────────────────────────────────
FEEDS = [
    # 예시: 원하는 카테고리의 RSS 주소로 자유롭게 교체하세요.
    "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "https://www.techmeme.com/feed.xml",
    "https://hnrss.org/frontpage",
]
TOP_N = 5
OUTPUT_FILE = Path(__file__).parent / "topics.json"
REQUEST_TIMEOUT = 10


def fetch_feed(url: str) -> list[dict]:
    """단일 RSS 피드를 가져와 (title, link, published) 리스트로 반환."""
    items = []
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "topic-collector/1.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f"  [경고] {url} 가져오기 실패: {e}")
        return items

    # RSS 2.0: channel/item, Atom: feed/entry 둘 다 대응
    for item in root.iter():
        tag = item.tag.split("}")[-1]  # 네임스페이스 제거
        if tag not in ("item", "entry"):
            continue

        title, link, pub = None, None, None
        for child in item:
            ctag = child.tag.split("}")[-1]
            if ctag == "title":
                title = (child.text or "").strip()
            elif ctag == "link":
                link = child.get("href") or (child.text or "").strip()
            elif ctag in ("pubDate", "published", "updated"):
                pub = (child.text or "").strip()

        if not title:
            continue

        published_dt = None
        if pub:
            try:
                published_dt = parsedate_to_datetime(pub)
            except Exception:
                try:
                    published_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                except Exception:
                    published_dt = None

        items.append({
            "title": title,
            "link": link,
            "source": url,
            "published": published_dt.isoformat() if published_dt else None,
        })

    return items


def score_topic(item: dict, now: datetime) -> float:
    """간단한 점수화: 최신일수록 높은 점수. 필요시 키워드 가중치 등을 추가하세요."""
    score = 1.0
    if item.get("published"):
        try:
            pub_dt = datetime.fromisoformat(item["published"])
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            hours_ago = max((now - pub_dt).total_seconds() / 3600, 0)
            # 24시간 이내면 가산점, 오래될수록 감점
            score += max(0, 5 - hours_ago / 4.8)
        except Exception:
            pass

    # 제목 길이가 너무 짧거나 광고성 문구면 감점 (원하는 대로 조정)
    if len(item["title"]) < 10:
        score -= 1

    return score


def dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for it in items:
        key = re.sub(r"\W+", "", it["title"].lower())[:60]
        if key in seen:
            continue
        seen.add(key)
        result.append(it)
    return result


def main():
    print("주제 수집 시작...")
    all_items = []
    for feed_url in FEEDS:
        print(f"- {feed_url} 확인 중")
        fetched = fetch_feed(feed_url)
        print(f"  -> {len(fetched)}건")
        all_items.extend(fetched)
        time.sleep(0.5)

    all_items = dedupe(all_items)
    now = datetime.now(timezone.utc)
    for it in all_items:
        it["score"] = round(score_topic(it, now), 3)

    ranked = sorted(all_items, key=lambda x: x["score"], reverse=True)
    top = ranked[:TOP_N]

    output = {
        "generated_at": now.isoformat(),
        "topics": top,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n총 {len(all_items)}건 수집, 상위 {len(top)}건 선정 -> {OUTPUT_FILE}")
    for i, t in enumerate(top, 1):
        print(f"  {i}. [{t['score']}] {t['title']}")


if __name__ == "__main__":
    main()
