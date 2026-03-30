"""
Tokyo Food Map - main.py
========================
YouTube Data API v3를 활용하여 지정된 채널의 영상 데이터를 수집하고,
하이브리드 점수(Final_Score)를 산출한 뒤 JSON 파일로 저장합니다.

사용법:
    1. .env 파일에 YOUTUBE_API_KEY를 설정하거나 환경변수로 지정하세요.
    2. python main.py 실행 시 restaurants.json 이 생성됩니다.
    3. 블로그용 HTML 코드는 터미널에 자동 출력됩니다.

주의:
    - Google 평점은 실제 스크래핑 없이 3.8~4.9 범위의 난수로 생성됩니다.
    - YouTube API 할당량(Quota)에 유의하세요.
"""

import os
import re
import json
import random
import html as html_module
from datetime import datetime

# ── 선택적 의존성 임포트 ──────────────────────────────────────────────────────
try:
    from googleapiclient.discovery import build
    YOUTUBE_API_AVAILABLE = True
except ImportError:
    YOUTUBE_API_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 미설치 시 환경변수 직접 사용

# ── 설정 상수 ─────────────────────────────────────────────────────────────────
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")

# 타겟 채널 목록 (채널명: 채널 ID)
TARGET_CHANNELS = {
    "도사남 DoSaNam":        "UCLESFh73weYSIAHZd3EEZjg",
    "토요일의 도쿄":          "UCDNdIbLRezC2RZdIvi5bxnQ",
    "SUSURU TV.":            "UCXcjvt8cOfwtcqaMeE7-hqA",
    "新宿グルメチャンネル":   "UCHXxEc5QCVbiSR0rW9qTacA",
    "Tokyo Gourmet":         "UC0_J_HiKEc4SG8E8_feekLA",
    "Cosper Gourmet":        "UCxF3FMkATZ3f6CEPBFgVobQ"
}

# 도쿄 세부 지역 키워드 → 지역명 매핑
REGION_KEYWORDS = {
    "新宿|신주쿠|shinjuku":         "신주쿠(新宿)",
    "渋谷|시부야|shibuya":          "시부야(渋谷)",
    "池袋|이케부쿠로|ikebukuro":    "이케부쿠로(池袋)",
    "銀座|긴자|ginza":              "긴자(銀座)",
    "浅草|아사쿠사|asakusa":        "아사쿠사(浅草)",
    "六本木|롯폰기|roppongi":       "롯폰기(六本木)",
    "恵比寿|에비스|ebisu":          "에비스(恵比寿)",
    "原宿|하라주쿠|harajuku":       "하라주쿠(原宿)",
    "秋葉原|아키하바라|akihabara":  "아키하바라(秋葉原)",
    "上野|우에노|ueno":             "우에노(上野)",
    "品川|시나가와|shinagawa":      "시나가와(品川)",
    "目黒|메구로|meguro":           "메구로(目黒)",
    "中目黒|나카메구로|nakameguro": "나카메구로(中目黒)",
    "下北沢|시모키타자와|shimokitazawa": "시모키타자와(下北沢)",
    "吉祥寺|기치조지|kichijoji":    "기치조지(吉祥寺)",
}

# 분위기 태그 키워드 사전 (영상 설명/제목 분석용)
ATMOSPHERE_KEYWORD_MAP = {
    "혼밥가능":    ["혼밥", "1인", "솔로", "혼자", "一人", "ひとり", "solo"],
    "시끌벅적":    ["시끌", "왁자지껄", "활기", "賑やか", "にぎやか", "lively", "busy"],
    "데이트":      ["데이트", "커플", "デート", "カップル", "couple", "romantic"],
    "가성비":      ["가성비", "저렴", "お得", "安い", "cheap", "budget", "affordable"],
    "프리미엄":    ["고급", "럭셔리", "プレミアム", "高級", "luxury", "premium", "fine dining"],
    "라멘":        ["라멘", "ラーメン", "ramen"],
    "스시":        ["스시", "초밥", "寿司", "すし", "sushi"],
    "야키니쿠":    ["야키니쿠", "焼肉", "やきにく", "yakiniku", "bbq"],
    "이자카야":    ["이자카야", "居酒屋", "izakaya"],
    "카페":        ["카페", "カフェ", "cafe", "coffee"],
    "줄서는맛집":  ["줄", "대기", "行列", "並ぶ", "queue", "wait"],
    "현지인추천":  ["현지인", "로컬", "地元", "local"],
    "야경맛집":    ["야경", "夜景", "night view", "rooftop"],
    "오마카세":    ["오마카세", "おまかせ", "omakase"],
    "딤섬":        ["딤섬", "飲茶", "dim sum", "dimsum"],
}

# ── 유틸리티 함수 ─────────────────────────────────────────────────────────────

def generate_google_rating() -> float:
    """
    Google 평점을 3.8 ~ 4.9 범위의 난수(소수점 첫째 자리)로 생성합니다.
    ⚠️ 실제 스크래핑 없이 임시 데이터로 사용됩니다.
    """
    return round(random.uniform(3.8, 4.9), 1)


def extract_region(text: str) -> str:
    """
    주소 또는 설명 텍스트에서 도쿄 세부 지역명을 추출합니다.
    """
    for pattern, region_name in REGION_KEYWORDS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return region_name
    return "도쿄(東京)"  # 기본값


def extract_atmosphere_tags(text: str) -> list[str]:
    """
    영상 제목/설명 텍스트를 분석하여 분위기 태그 리스트를 반환합니다.
    """
    tags = []
    text_lower = text.lower()
    for tag, keywords in ATMOSPHERE_KEYWORD_MAP.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                tags.append(tag)
                break
    return tags if tags else ["도쿄맛집"]


def extract_google_map_url(text: str) -> str:
    """
    영상 설명에서 Google Maps URL을 추출합니다.
    maps.google.com / goo.gl/maps / google.com/maps 형식 지원.
    """
    patterns = [
        r"https?://(?:www\.)?google\.com/maps/place/[^\s\)\"']+",
        r"https?://goo\.gl/maps/[^\s\)\"']+",
        r"https?://maps\.google\.com/[^\s\)\"']+",
        r"https?://maps\.app\.goo\.gl/[^\s\)\"']+",
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            return match.group(0)
    return ""


def calculate_final_score(overlap_count: int, google_rating: float) -> float:
    """
    하이브리드 점수 산출 공식:
        Final_Score = (Min(Overlap_Count, 5) * 10) + (Google_Rating * 10)
    최대 약 100점 (Overlap 5회 * 10 + 평점 5.0 * 10 = 100)
    """
    return round((min(overlap_count, 5) * 10) + (google_rating * 10), 1)


def get_thumbnail_url(video_id: str, quality: str = "maxresdefault") -> str:
    """
    YouTube 영상 ID로 썸네일 URL을 생성합니다.
    quality: maxresdefault | hqdefault | mqdefault | sddefault
    """
    return f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"


# ── YouTube API 연동 함수 ─────────────────────────────────────────────────────

def fetch_channel_videos(youtube_client, channel_id: str, max_results: int = 30) -> list[dict]:
    """
    채널 ID로 최신 영상 목록을 가져옵니다.
    """
    videos = []
    try:
        # 채널의 업로드 플레이리스트 ID 조회
        channel_response = youtube_client.channels().list(
            part="contentDetails,snippet",
            id=channel_id
        ).execute()

        if not channel_response.get("items"):
            print(f"  ⚠️  채널 ID '{channel_id}' 를 찾을 수 없습니다.")
            return []

        channel_info = channel_response["items"][0]
        uploads_playlist_id = (
            channel_info["contentDetails"]["relatedPlaylists"]["uploads"]
        )
        channel_title = channel_info["snippet"]["title"]

        # 플레이리스트에서 영상 목록 조회
        playlist_response = youtube_client.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=max_results
        ).execute()

        for item in playlist_response.get("items", []):
            snippet = item["snippet"]
            video_id = snippet["resourceId"]["videoId"]
            description = snippet.get("description", "")
            title = snippet.get("title", "")

            # Google Maps URL 추출
            map_url = extract_google_map_url(description)
            if not map_url:
                # 맵 링크 없는 영상은 스킵 (맛집 영상이 아닐 가능성)
                continue

            # 영상 상세 정보 조회 (통계 포함)
            video_detail = youtube_client.videos().list(
                part="snippet,statistics",
                id=video_id
            ).execute()

            view_count = 0
            if video_detail.get("items"):
                stats = video_detail["items"][0].get("statistics", {})
                view_count = int(stats.get("viewCount", 0))

            combined_text = f"{title} {description}"
            region = extract_region(combined_text)
            atm_tags = extract_atmosphere_tags(combined_text)

            videos.append({
                "video_id":    video_id,
                "title":       title,
                "description": description[:500],  # 500자 제한
                "channel":     channel_title,
                "map_url":     map_url,
                "region":      region,
                "atm_tags":    atm_tags,
                "view_count":  view_count,
                "thumbnail":   get_thumbnail_url(video_id),
                "published_at": snippet.get("publishedAt", ""),
            })

        print(f"  ✅ '{channel_title}' 채널에서 {len(videos)}개 맛집 영상 수집 완료")

    except Exception as e:
        print(f"  ❌ 채널 '{channel_id}' 처리 중 오류: {e}")

    return videos


def aggregate_restaurants(all_videos: list[dict]) -> list[dict]:
    """
    여러 채널의 영상 데이터를 집계하여 식당별 중첩 횟수를 계산합니다.
    Google Maps URL을 기준으로 동일 식당을 식별합니다.
    """
    restaurant_map: dict[str, dict] = {}

    for video in all_videos:
        map_url = video["map_url"]
        if not map_url:
            continue

        # URL 정규화 (쿼리 파라미터 제거)
        base_url = map_url.split("?")[0].rstrip("/")

        if base_url not in restaurant_map:
            google_rating = generate_google_rating()
            restaurant_map[base_url] = {
                "id":                 f"rest_{abs(hash(base_url)) % 100000:05d}",
                "name":               _extract_restaurant_name(video["title"]),
                "map_url":            map_url,
                "region":             video["region"],
                "address":            _extract_address(video["description"]),
                "atmosphere_tags":    video["atm_tags"],
                "overlap_count":      1,
                "channels":           [video["channel"]],
                "google_rating":      google_rating,
                "restaurant_thumbnail": video["thumbnail"],
                "video_id":           video["video_id"],
                "published_at":       video["published_at"],
                "view_count":         video["view_count"],
            }
        else:
            entry = restaurant_map[base_url]
            entry["overlap_count"] += 1
            if video["channel"] not in entry["channels"]:
                entry["channels"].append(video["channel"])
            # 분위기 태그 병합 (중복 제거)
            for tag in video["atm_tags"]:
                if tag not in entry["atmosphere_tags"]:
                    entry["atmosphere_tags"].append(tag)
            # 조회수 높은 썸네일로 교체
            if video["view_count"] > entry["view_count"]:
                entry["restaurant_thumbnail"] = video["thumbnail"]
                entry["video_id"] = video["video_id"]
                entry["view_count"] = video["view_count"]

    # Final_Score 계산
    restaurants = list(restaurant_map.values())
    for r in restaurants:
        r["final_score"] = calculate_final_score(
            r["overlap_count"], r["google_rating"]
        )

    # Final_Score 내림차순 정렬
    restaurants.sort(key=lambda x: x["final_score"], reverse=True)
    return restaurants


def _extract_restaurant_name(title: str) -> str:
    """
    영상 제목에서 식당명을 추출합니다 (휴리스틱 방식).
    """
    # 대괄호, 소괄호 안의 내용 제거
    cleaned = re.sub(r"[\[\(【「].*?[\]\)】」]", "", title).strip()
    # 특수문자 및 과도한 공백 정리
    cleaned = re.sub(r"[|｜/／]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # 50자 초과 시 앞부분만 사용
    return cleaned[:50] if len(cleaned) > 50 else cleaned or title[:50]


def _extract_address(description: str) -> str:
    """
    영상 설명에서 주소를 추출합니다 (일본 주소 패턴 매칭).
    """
    # 일본 주소 패턴: 東京都 / 도쿄도 로 시작하는 문자열
    patterns = [
        r"東京都[^\n\r,，。]{5,60}",
        r"〒\d{3}-\d{4}[^\n\r]{5,60}",
        r"住所[：:]\s*([^\n\r]{5,60})",
        r"Address[：:]\s*([^\n\r]{5,60})",
        r"주소[：:]\s*([^\n\r]{5,60})",
    ]
    for pat in patterns:
        match = re.search(pat, description)
        if match:
            addr = match.group(0) if "(" not in pat else match.group(1)
            return addr.strip()[:80]
    return "도쿄도 (상세 주소 미기재)"


# ── 샘플 데이터 생성 (API 키 없을 때 사용) ────────────────────────────────────

SAMPLE_RESTAURANTS = [
    {
        "name": "一蘭 新宿店 (이치란 신주쿠)",
        "region": "신주쿠(新宿)",
        "address": "東京都新宿区歌舞伎町1-22-7",
        "map_url": "https://www.google.com/maps/place/Ichiran+Shinjuku",
        "atmosphere_tags": ["혼밥가능", "라멘", "줄서는맛집"],
        "channels": ["도사남 DoSaNam", "SUSURU TV."],
        "video_id": "dQw4w9WgXcQ",
    },
    {
        "name": "すきやばし次郎 本店 (스키야바시 지로)",
        "region": "긴자(銀座)",
        "address": "東京都中央区銀座4-2-15 塚本素山ビルB1F",
        "map_url": "https://www.google.com/maps/place/Sukiyabashi+Jiro+Honten",
        "atmosphere_tags": ["오마카세", "프리미엄", "스시"],
        "channels": ["Tokyo Gourmet", "Cosper Gourmet", "토요일의 도쿄"],
        "video_id": "oHg5SJYRHA0",
    },
    {
        "name": "焼肉ライク 渋谷店 (야키니쿠 라이크 시부야)",
        "region": "시부야(渋谷)",
        "address": "東京都渋谷区道玄坂2-25-8",
        "map_url": "https://www.google.com/maps/place/Yakiniku+Like+Shibuya",
        "atmosphere_tags": ["혼밥가능", "야키니쿠", "가성비"],
        "channels": ["도사남 DoSaNam", "토요일의 도쿄"],
        "video_id": "9bZkp7q19f0",
    },
    {
        "name": "鳥貴族 池袋東口店 (토리키조쿠 이케부쿠로)",
        "region": "이케부쿠로(池袋)",
        "address": "東京都豊島区東池袋1-13-8",
        "map_url": "https://www.google.com/maps/place/Torikizoku+Ikebukuro",
        "atmosphere_tags": ["이자카야", "시끌벅적", "가성비"],
        "channels": ["新宿グルメチャンネル", "SUSURU TV."],
        "video_id": "kffacxfA7G4",
    },
    {
        "name": "中本 六本木店 (나카모토 롯폰기)",
        "region": "롯폰기(六本木)",
        "address": "東京都港区六本木3-14-12",
        "map_url": "https://www.google.com/maps/place/Nakamoto+Roppongi",
        "atmosphere_tags": ["라멘", "현지인추천", "시끌벅적"],
        "channels": ["Tokyo Gourmet", "도사남 DoSaNam", "新宿グルメチャンネル"],
        "video_id": "L_jWHffIx5E",
    },
    {
        "name": "浅草 むぎとオリーブ (아사쿠사 무기토 올리브)",
        "region": "아사쿠사(浅草)",
        "address": "東京都台東区浅草1-36-8",
        "map_url": "https://www.google.com/maps/place/Mugi+to+Olive+Asakusa",
        "atmosphere_tags": ["라멘", "줄서는맛집", "현지인추천"],
        "channels": ["SUSURU TV.", "Cosper Gourmet"],
        "video_id": "fJ9rUzIMcZQ",
    },
    {
        "name": "恵比寿 AFURI (아후리 에비스)",
        "region": "에비스(恵比寿)",
        "address": "東京都渋谷区恵比寿1-1-7",
        "map_url": "https://www.google.com/maps/place/AFURI+Ebisu",
        "atmosphere_tags": ["라멘", "데이트", "프리미엄"],
        "channels": ["토요일의 도쿄", "Tokyo Gourmet", "Cosper Gourmet"],
        "video_id": "hT_nvWreIhg",
    },
    {
        "name": "中目黒 蔦 (나카메구로 츠타)",
        "region": "나카메구로(中目黒)",
        "address": "東京都目黒区上目黒2-47-12",
        "map_url": "https://www.google.com/maps/place/Tsuta+Nakameguro",
        "atmosphere_tags": ["라멘", "프리미엄", "줄서는맛집"],
        "channels": ["SUSURU TV.", "도사남 DoSaNam", "新宿グルメチャンネル", "Tokyo Gourmet"],
        "video_id": "CevxZvSJLk8",
    },
    {
        "name": "原宿 Kawaii Monster Cafe (카와이이 몬스터 카페)",
        "region": "하라주쿠(原宿)",
        "address": "東京都渋谷区神宮前4-31-10",
        "map_url": "https://www.google.com/maps/place/Kawaii+Monster+Cafe",
        "atmosphere_tags": ["카페", "데이트", "시끌벅적"],
        "channels": ["토요일의 도쿄", "Cosper Gourmet"],
        "video_id": "YQHsXMglC9A",
    },
    {
        "name": "秋葉原 神田カレー (아키하바라 칸다 카레)",
        "region": "아키하바라(秋葉原)",
        "address": "東京都千代田区外神田1-15-16",
        "map_url": "https://www.google.com/maps/place/Kanda+Curry+Akihabara",
        "atmosphere_tags": ["가성비", "현지인추천", "혼밥가능"],
        "channels": ["新宿グルメチャンネル", "도사남 DoSaNam"],
        "video_id": "tgbNymZ7vqY",
    },
    {
        "name": "上野 精養軒 (우에노 세이요켄)",
        "region": "우에노(上野)",
        "address": "東京都台東区上野公園4-58",
        "map_url": "https://www.google.com/maps/place/Seiyoken+Ueno",
        "atmosphere_tags": ["프리미엄", "데이트", "야경맛집"],
        "channels": ["Tokyo Gourmet", "토요일의 도쿄", "Cosper Gourmet"],
        "video_id": "pRpeEdMmmQ0",
    },
    {
        "name": "下北沢 カレーの店 ボンベイ (시모키타자와 봄베이)",
        "region": "시모키타자와(下北沢)",
        "address": "東京都世田谷区北沢2-14-17",
        "map_url": "https://www.google.com/maps/place/Bombay+Shimokitazawa",
        "atmosphere_tags": ["가성비", "현지인추천", "혼밥가능"],
        "channels": ["도사남 DoSaNam", "新宿グルメチャンネル", "SUSURU TV."],
        "video_id": "OPf0YbXqDm0",
    },
    {
        "name": "吉祥寺 いせや総本店 (기치조지 이세야)",
        "region": "기치조지(吉祥寺)",
        "address": "東京都武蔵野市吉祥寺南町1-15-8",
        "map_url": "https://www.google.com/maps/place/Iseya+Kichijoji",
        "atmosphere_tags": ["이자카야", "시끌벅적", "현지인추천"],
        "channels": ["토요일의 도쿄", "Cosper Gourmet", "Tokyo Gourmet"],
        "video_id": "M7lc1UVf-VE",
    },
    {
        "name": "品川 天王洲 T.Y.HARBOR (티와이하버)",
        "region": "시나가와(品川)",
        "address": "東京都品川区東品川2-1-3",
        "map_url": "https://www.google.com/maps/place/TY+Harbor+Shinagawa",
        "atmosphere_tags": ["데이트", "야경맛집", "프리미엄"],
        "channels": ["Tokyo Gourmet", "토요일의 도쿄"],
        "video_id": "60ItHLz5WEA",
    },
    {
        "name": "目黒 権之助坂 とんき (메구로 톤키)",
        "region": "메구로(目黒)",
        "address": "東京都目黒区下目黒1-1-2",
        "map_url": "https://www.google.com/maps/place/Tonki+Meguro",
        "atmosphere_tags": ["현지인추천", "줄서는맛집", "가성비"],
        "channels": ["도사남 DoSaNam", "SUSURU TV.", "Cosper Gourmet", "新宿グルメチャンネル"],
        "video_id": "BQ0mxQXmLsk",
    },
]


def generate_sample_data() -> list[dict]:
    """
    API 키 없이 사용할 수 있는 샘플 데이터를 생성합니다.
    Google 평점은 매 실행 시 난수로 재생성됩니다.
    """
    restaurants = []
    for i, item in enumerate(SAMPLE_RESTAURANTS):
        google_rating = generate_google_rating()
        overlap_count = len(item["channels"])
        final_score = calculate_final_score(overlap_count, google_rating)

        restaurants.append({
            "id":                    f"rest_{i+1:03d}",
            "name":                  item["name"],
            "region":                item["region"],
            "address":               item["address"],
            "map_url":               item["map_url"],
            "atmosphere_tags":       item["atmosphere_tags"],
            "overlap_count":         overlap_count,
            "channels":              item["channels"],
            "google_rating":         google_rating,
            "final_score":           final_score,
            "restaurant_thumbnail":  get_thumbnail_url(item["video_id"]),
            "video_id":              item["video_id"],
            "published_at":          datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "view_count":            random.randint(50000, 5000000),
        })

    # Final_Score 내림차순 정렬
    restaurants.sort(key=lambda x: x["final_score"], reverse=True)
    return restaurants


# ── 블로그 HTML 출력 함수 ──────────────────────────────────────────────────────

def generate_blog_html(restaurants: list[dict], top_n: int = 10) -> str:
    """
    상위 N개 맛집 정보를 블로그용 HTML 코드로 생성합니다.
    대상 블로그: https://www.google.com/search?q=eule-bwong.tistory.com
    """
    top_restaurants = restaurants[:top_n]

    html_parts = [
        "<!-- ============================================================ -->",
        "<!-- 도쿄 맛집 TOP 10 - eule-bwong.tistory.com 블로그용 HTML 코드 -->",
        "<!-- 생성일: " + datetime.now().strftime("%Y년 %m월 %d일") + " -->",
        "<!-- ============================================================ -->",
        "",
        '<div class="tokyo-food-top10" style="font-family:\'Noto Sans KR\',sans-serif;max-width:800px;margin:0 auto;">',
        '  <h2 style="font-size:28px;font-weight:900;color:#0047AB;border-bottom:4px solid #0047AB;padding-bottom:12px;">',
        '    🗼 도쿄 맛집 TOP 10 | 유튜버 교차 추천 하이브리드 점수 순위',
        '  </h2>',
        '  <p style="color:#666;font-size:14px;margin-bottom:24px;">',
        f'    한국·일본 유명 유튜버 {len(TARGET_CHANNELS)}개 채널 교차 분석 기반 | 하이브리드 점수 = (중첩횟수×10) + (구글평점×10)',
        '  </p>',
    ]

    for rank, r in enumerate(top_restaurants, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")
        tags_html = " ".join(
            f'<span style="background:#0047AB;color:#fff;padding:2px 8px;border-radius:12px;font-size:12px;margin:2px;">{html_module.escape(t)}</span>'
            for t in r["atmosphere_tags"]
        )
        channels_str = " · ".join(r["channels"])

        html_parts += [
            f'  <div style="display:flex;gap:16px;margin-bottom:24px;padding:16px;border:2px solid #eee;border-radius:8px;">',
            f'    <div style="flex-shrink:0;width:160px;">',
            f'      <img src="{html_module.escape(r["restaurant_thumbnail"])}" alt="{html_module.escape(r["name"])}"',
            f'           style="width:160px;height:90px;object-fit:cover;border-radius:4px;" />',
            f'    </div>',
            f'    <div style="flex:1;">',
            f'      <div style="font-size:22px;font-weight:900;color:#0047AB;margin-bottom:4px;">{medal} <a href="{html_module.escape(r["map_url"])}" target="_blank" style="color:#0047AB;text-decoration:none;border-bottom:2px solid #0047AB;padding-bottom:1px;transition:opacity 0.2s;" onmouseover="this.style.opacity=0.7" onmouseout="this.style.opacity=1">{html_module.escape(r["name"])}</a></div>',
            f'      <div style="font-size:13px;color:#888;margin-bottom:6px;">📍 {html_module.escape(r["region"])} | {html_module.escape(r["address"])}</div>',
            f'      <div style="margin-bottom:6px;">{tags_html}</div>',
            f'      <div style="font-size:13px;color:#555;">',
            f'        ⭐ 구글 평점: <strong>{r["google_rating"]}</strong> &nbsp;|&nbsp;',
            f'        🔁 유튜버 중첩: <strong>{r["overlap_count"]}회</strong> &nbsp;|&nbsp;',
            f'        🏆 하이브리드 점수: <strong style="color:#0047AB;">{r["final_score"]}점</strong>',
            f'      </div>',
            f'      <div style="font-size:12px;color:#aaa;margin-top:4px;">📺 {html_module.escape(channels_str)}</div>',
            f'      <div style="margin-top:8px;">',
            f'        <a href="{html_module.escape(r["map_url"])}" target="_blank"',
            f'           style="background:#0047AB;color:#fff;padding:4px 12px;border-radius:4px;text-decoration:none;font-size:13px;">',
            f'          🗺️ 구글 맵 보기</a>',
            f'      </div>',
            f'    </div>',
            f'  </div>',
        ]

    html_parts += [
        '</div>',
        "",
        "<!-- 위 HTML을 티스토리 HTML 편집 모드에 붙여넣기 하세요 -->",
    ]

    return "\n".join(html_parts)


# ── 메인 실행 ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  🗼 Tokyo Food Map - 데이터 수집 & 점수 산출 시스템")
    print("=" * 60)

    restaurants: list[dict] = []

    if YOUTUBE_API_KEY and YOUTUBE_API_AVAILABLE:
        print("\n[1/3] YouTube Data API v3 연결 중...")
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        all_videos: list[dict] = []
        for channel_name, channel_id in TARGET_CHANNELS.items():
            print(f"  → '{channel_name}' 채널 수집 중...")
            videos = fetch_channel_videos(youtube, channel_id, max_results=30)
            all_videos.extend(videos)

        print(f"\n[2/3] 총 {len(all_videos)}개 영상 집계 및 중첩 분석 중...")
        restaurants = aggregate_restaurants(all_videos)

        if not restaurants:
            print("  ⚠️  API 수집 결과가 없습니다. 샘플 데이터로 대체합니다.")
            restaurants = generate_sample_data()
    else:
        if not YOUTUBE_API_KEY:
            print("\n⚠️  YOUTUBE_API_KEY 환경변수가 설정되지 않았습니다.")
            print("   → 샘플 데이터(15개 식당)로 restaurants.json을 생성합니다.")
        elif not YOUTUBE_API_AVAILABLE:
            print("\n⚠️  google-api-python-client 미설치.")
            print("   → 샘플 데이터(15개 식당)로 restaurants.json을 생성합니다.")

        print("\n[1/3] 샘플 데이터 생성 중 (Google 평점 난수 생성)...")
        restaurants = generate_sample_data()

    print(f"\n[2/3] {len(restaurants)}개 식당 데이터 처리 완료")
    for i, r in enumerate(restaurants[:5], 1):
        print(f"  {i}. {r['name'][:30]:<30} | 점수: {r['final_score']:5.1f} | 평점: {r['google_rating']} | 중첩: {r['overlap_count']}회")
    if len(restaurants) > 5:
        print(f"  ... 외 {len(restaurants)-5}개")

    # JSON 저장
    output_path = os.path.join(os.path.dirname(__file__), "restaurants.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(restaurants, f, ensure_ascii=False, indent=2)
    print(f"\n✅ restaurants.json 저장 완료: {output_path}")

    # 블로그 HTML 출력
    print("\n[3/3] 블로그용 HTML 코드 생성 중...")
    blog_html = generate_blog_html(restaurants, top_n=10)

    blog_html_path = os.path.join(os.path.dirname(__file__), "blog_top10.html")
    with open(blog_html_path, "w", encoding="utf-8") as f:
        f.write(blog_html)

    print("\n" + "=" * 60)
    print("  📝 블로그용 HTML 코드 (상위 10개 맛집)")
    print("  → eule-bwong.tistory.com 에 붙여넣기용")
    print("=" * 60)
    print(blog_html)
    print("=" * 60)
    print(f"\n✅ blog_top10.html 저장 완료: {blog_html_path}")
    print("\n🎉 모든 처리 완료!")


if __name__ == "__main__":
    main()
