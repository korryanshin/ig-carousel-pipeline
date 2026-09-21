# 인스타그램 캐러셀 자동화 파이프라인

주제 수집 → 텔레그램으로 후보 발송 → 사용자가 버튼으로 선택 → 캐러셀 이미지 생성 →
인스타그램 자동 업로드까지 GitHub Actions에서 무료로 돌아가는 파이프라인입니다.

## 전체 흐름

```
[매일 09:00 KST] collect_and_notify.yml
  1. collect_topics.py  : RSS에서 주제 수집, 상위 5개 topics.json 저장
  2. send_to_telegram.py: 상위 주제를 인라인 버튼과 함께 텔레그램 발송

[15분마다] check_and_publish.yml
  3. check_selection.py     : 텔레그램에서 새 버튼 선택이 있었는지 확인
                               있으면 캐러셀 이미지 생성 (output/<날짜-슬러그>/*.png)
  4. (git commit & push)    : 이미지를 저장소에 반영해 raw.githubusercontent.com으로 공개
  5. publish_to_instagram.py: raw URL로 Instagram Graph API 캐러셀 업로드
```

## 처음 설정하기 (순서대로)

### 1. 이 폴더를 GitHub 저장소로 만들기
1. github.com에서 새 저장소 생성 (반드시 **Public**으로 — 이미지가 공개 URL로 접근돼야
   인스타그램이 가져갈 수 있습니다)
2. 이 폴더 전체를 그 저장소에 push
   ```bash
   cd ig-carousel-pipeline
   git init
   git add .
   git commit -m "init: 인스타 캐러셀 자동화 파이프라인"
   git branch -M main
   git remote add origin https://github.com/<본인계정>/<저장소이름>.git
   git push -u origin main
   ```

### 2. 텔레그램 봇 만들기
1. 텔레그램 앱에서 **@BotFather** 검색 → `/newbot` 실행 → 이름 설정
2. 발급된 **봇 토큰** 저장 (예: `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
3. 방금 만든 봇과 대화를 한 번 시작 (아무 메시지나 전송)
4. 브라우저로 아래 주소 접속해서 본인의 **chat id** 확인:
   ```
   https://api.telegram.org/bot<봇토큰>/getUpdates
   ```
   응답 JSON 안의 `"chat":{"id": 123456789, ...}` 값이 chat id 입니다.

### 3. 인스타그램 Graph API 준비
1. 인스타그램 계정을 **비즈니스 또는 크리에이터 계정**으로 전환
2. Facebook 페이지를 만들고 인스타그램 계정과 연결
3. [Facebook for Developers](https://developers.facebook.com) 에서 앱 생성
   → 제품 추가에서 **Instagram Graph API** 추가
4. Graph API Explorer 등에서 아래 권한으로 액세스 토큰 발급:
   - `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`
5. 단기 토큰을 **장기(60일) 토큰**으로 교환 (Graph API Explorer 또는 아래 curl 참고)
   ```
   GET https://graph.facebook.com/v21.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id=<앱ID>
     &client_secret=<앱시크릿>
     &fb_exchange_token=<단기토큰>
   ```
6. 본인 **Instagram 비즈니스 계정 ID** 확인:
   ```
   GET https://graph.facebook.com/v21.0/me/accounts?access_token=<토큰>
   ```
   → 나온 페이지 ID로 아래 호출:
   ```
   GET https://graph.facebook.com/v21.0/<페이지ID>?fields=instagram_business_account&access_token=<토큰>
   ```

> ⚠️ 장기 토큰도 60일 후 만료됩니다. 만료 전에 갱신해서 GitHub Secret 값을 업데이트해야
> 자동화가 끊기지 않습니다. (나중에 자동 갱신 스크립트를 추가할 수도 있습니다.)

### 4. GitHub 저장소에 Secrets 등록
저장소 → Settings → Secrets and variables → Actions → New repository secret 에서 아래 4개 등록:

| Secret 이름 | 값 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 2번에서 발급받은 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 2번에서 확인한 chat id |
| `IG_ACCESS_TOKEN` | 3번에서 발급받은 장기 액세스 토큰 |
| `IG_BUSINESS_ACCOUNT_ID` | 3번에서 확인한 인스타그램 비즈니스 계정 ID |

### 5. 동작 확인
1. 저장소 → Actions 탭 → "주제 수집 및 텔레그램 발송" 워크플로우 → **Run workflow** 로 수동 실행
2. 텔레그램으로 주제 후보 + 버튼 메시지가 오는지 확인
3. 버튼 하나를 눌러 선택
4. Actions 탭 → "텔레그램 선택 확인 및 인스타그램 업로드" → **Run workflow** 로 수동 실행
   (평소엔 15분마다 자동 실행됨)
5. 인스타그램 계정에 캐러셀 게시물이 올라오는지 확인

## 커스터마이징 포인트

- **주제 소스 바꾸기**: `collect_topics.py` 의 `FEEDS` 리스트를 원하는 RSS로 교체
- **점수화 기준 바꾸기**: `collect_topics.py` 의 `score_topic()` 함수 수정
- **슬라이드 디자인 바꾸기**: `generate_carousel.py` 의 `render_slide()` 함수 수정
  (지금은 심플한 텍스트 카드; 나중에 원하는 템플릿이 정해지면 여기를 교체하면 됩니다)
- **본문 카피 자동 생성**: `check_selection.py` 안의 `bullets = [...]` 부분을
  Claude API 등을 호출해 주제에 맞는 카피를 만들도록 교체 가능
- **발송/확인 주기 바꾸기**: `.github/workflows/*.yml` 의 `cron` 값 수정
  (cron은 UTC 기준 — 한국시간(KST)은 UTC+9)

## 알아두면 좋은 점

- GitHub Actions 무료 티어는 public 저장소는 무제한, private 저장소는 월 2,000분까지 무료입니다.
  15분마다 실행되는 워크플로우는 한 달 약 2,900회 실행되지만 매번 몇 초~1분 내로 끝나므로
  public 저장소라면 비용 걱정이 없습니다.
- 이미지가 저장소에 계속 쌓이므로, 주기적으로 `output/` 의 오래된 폴더를 정리하는 것을 권장합니다.
- 만약 나중에 private 저장소로 바꾸고 싶다면, 이미지 호스팅 방식을 별도 스토리지(S3, Cloudinary 등)로
  바꿔야 합니다 (raw.githubusercontent.com은 public 저장소에서만 공개 접근이 가능합니다).
