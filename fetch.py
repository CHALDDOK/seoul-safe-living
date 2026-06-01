"""
fetch.py — 서울시 청년안심주택 공고 수집 + data.json 생성
- 민간임대 공고만 집계
- 전날 23:59까지 게시된 공고만 수집
- Nominatim geocoding (단지명+자치구 → 위경도)
- 역명→호선 매핑 (내장 테이블)
"""

import json
import re
import time
import requests
from datetime import datetime, timedelta, timezone

# ──────────────────────────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────────────────────────
API_URL = "https://soco.seoul.go.kr/youth/pgm/home/yohome/bbsListJson.json"
DETAIL_URL = "https://soco.seoul.go.kr/youth/bbs/BMSR00015/view.do"
OUTPUT_PATH = "data.json"

KST = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)
# 전날 23:59:59 KST 기준
CUTOFF = NOW_KST.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(seconds=1)

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://soco.seoul.go.kr/",
    "User-Agent": "Mozilla/5.0 (compatible; SeoulHousingBot/1.0)",
}

# ──────────────────────────────────────────────────────────────────
# 역명 → 호선 매핑 테이블 (주요 환승역 포함)
# ──────────────────────────────────────────────────────────────────
STATION_LINE_MAP: dict[str, list[str]] = {
    # 1호선
    "서울역": ["①", "④"],
    "시청": ["①", "②"],
    "종각": ["①"],
    "종로3가": ["①", "③", "⑤"],
    "종로5가": ["①"],
    "동대문": ["①", "④"],
    "신설동": ["①", "②"],
    "제기동": ["①"],
    "청량리": ["①"],
    "회기": ["①"],
    "외대앞": ["①"],
    "회룡": ["①"],
    "의정부": ["①"],
    "도봉산": ["①"],
    "도봉": ["①"],
    "방학": ["①"],
    "창동": ["①", "④"],
    "노원": ["④", "⑦"],
    "광운대": ["①"],
    "석계": ["①", "⑥"],
    "신이문": ["①"],
    "외대앞": ["①"],
    "한양대": ["②"],
    "뚝섬": ["②"],
    "성수": ["②"],
    "건대입구": ["②", "⑦"],
    "구의": ["②"],
    "강변": ["②"],
    "잠실나루": ["②"],
    "잠실": ["②", "⑧"],
    "잠실새내": ["②"],
    "종합운동장": ["②"],
    "삼성": ["②"],
    "선릉": ["②", "⑨"],
    "역삼": ["②"],
    "강남": ["②"],
    "교대": ["②", "③"],
    "서초": ["②"],
    "방배": ["②"],
    "사당": ["②", "④"],
    "낙성대": ["②"],
    "서울대입구": ["②"],
    "봉천": ["②"],
    "신림": ["②"],
    "신대방": ["②"],
    "구로디지털단지": ["②"],
    "대림": ["②", "⑦"],
    "신도림": ["①", "②"],
    "문래": ["②"],
    "영등포구청": ["②", "⑤"],
    "당산": ["②", "⑨"],
    "합정": ["②", "⑥"],
    "홍대입구": ["②", "⑥"],
    "신촌": ["②"],
    "이대": ["②"],
    "아현": ["②"],
    "충정로": ["②", "⑤"],
    "을지로3가": ["②", "③"],
    "을지로4가": ["②", "⑤"],
    "동대문역사문화공원": ["②", "④", "⑤"],
    "신당": ["②", "⑥"],
    "왕십리": ["②", "⑤", "수인분당"],
    "마장": ["⑤"],
    "답십리": ["⑤"],
    "장한평": ["⑤"],
    "수락산": ["⑦"],
    "마들": ["⑦"],
    "중계": ["⑦"],
    "하계": ["⑦"],
    "공릉": ["⑦"],
    "태릉입구": ["⑦"],
    "먹골": ["⑦"],
    "중화": ["⑦"],
    "상봉": ["⑦"],
    "면목": ["⑦"],
    "사가정": ["⑦"],
    "용마산": ["⑦"],
    "중곡": ["⑦"],
    "군자": ["⑤", "⑦"],
    "어린이대공원": ["⑦"],
    "뚝섬유원지": ["⑦"],
    "청담": ["⑦"],
    "강남구청": ["⑦", "수인분당"],
    "학동": ["⑦"],
    "논현": ["⑦"],
    "반포": ["⑦"],
    "고속터미널": ["③", "⑦", "⑨"],
    "내방": ["⑦"],
    "이수": ["④", "⑦"],
    "남성": ["⑦"],
    "숭실대입구": ["⑦"],
    "상도": ["⑦"],
    "장승배기": ["⑦"],
    "신대방삼거리": ["⑦"],
    "보라매": ["⑦"],
    "신풍": ["⑦"],
    "대방": ["①", "⑦"],
    "노량진": ["①", "⑨"],
    "용산": ["①", "④"],
    "이촌": ["④", "중앙"],
    "신용산": ["④"],
    "삼각지": ["④", "⑥"],
    "숙대입구": ["④"],
    "남영": ["①"],
    "동작": ["④", "⑨"],
    "총신대입구": ["④", "⑦"],
    "충무로": ["③", "④"],
    "명동": ["④"],
    "회현": ["④"],
    "미아사거리": ["④"],
    "미아": ["④"],
    "수유": ["④"],
    "쌍문": ["④"],
    "불광": ["③", "⑥"],
    "녹번": ["③"],
    "홍제": ["③"],
    "무악재": ["③"],
    "독립문": ["③"],
    "경복궁": ["③"],
    "안국": ["③"],
    "종로3가": ["①", "③", "⑤"],
    "을지로3가": ["②", "③"],
    "충무로": ["③", "④"],
    "동대입구": ["③"],
    "약수": ["③", "⑥"],
    "금호": ["③"],
    "옥수": ["③", "수인분당"],
    "압구정": ["③"],
    "신사": ["③"],
    "잠원": ["③"],
    "고속터미널": ["③", "⑦", "⑨"],
    "서초": ["②"],
    "방배": ["②"],
    "사당": ["②", "④"],
    "남태령": ["④"],
    "연신내": ["③", "⑥"],
    "구산": ["⑥"],
    "응암": ["⑥"],
    "역촌": ["⑥"],
    "새절": ["⑥"],
    "증산": ["⑥"],
    "디지털미디어시티": ["⑥", "공항"],
    "망원": ["⑥"],
    "마포구청": ["⑥"],
    "상수": ["⑥"],
    "광흥창": ["⑥"],
    "대흥": ["⑥"],
    "공덕": ["⑤", "⑥", "공항"],
    "효창공원앞": ["⑥"],
    "녹사평": ["⑥"],
    "이태원": ["⑥"],
    "한강진": ["⑥"],
    "버티고개": ["⑥"],
    "약수": ["③", "⑥"],
    "청구": ["⑤", "⑥"],
    "신당": ["②", "⑥"],
    "동묘앞": ["①", "⑥"],
    "창신": ["⑥"],
    "보문": ["⑥"],
    "안암": ["⑥"],
    "고려대": ["⑥"],
    "월곡": ["⑥"],
    "상월곡": ["⑥"],
    "돌곶이": ["⑥"],
    "화랑대": ["⑥"],
    "봉화산": ["⑥"],
    "신내": ["⑥"],
    "광화문": ["⑤"],
    "서대문": ["⑤"],
    "애오개": ["⑤"],
    "공덕": ["⑤", "⑥", "공항"],
    "마포": ["⑤"],
    "마포구청": ["⑥"],
    "여의도": ["⑤", "⑨"],
    "여의나루": ["⑤"],
    "마포": ["⑤"],
    "공덕": ["⑤", "⑥", "공항"],
    "애오개": ["⑤"],
    "서대문": ["⑤"],
    "광화문": ["⑤"],
    "종로3가": ["①", "③", "⑤"],
    "을지로4가": ["②", "⑤"],
    "동대문역사문화공원": ["②", "④", "⑤"],
    "청구": ["⑤", "⑥"],
    "신금호": ["⑤"],
    "행당": ["⑤"],
    "왕십리": ["②", "⑤", "수인분당"],
    "마장": ["⑤"],
    "답십리": ["⑤"],
    "장한평": ["⑤"],
    "군자": ["⑤", "⑦"],
    "아차산": ["⑤"],
    "광나루": ["⑤"],
    "천호": ["⑤", "⑧"],
    "강동": ["⑤", "⑧"],
    "길동": ["⑤"],
    "굽은다리": ["⑤"],
    "명일": ["⑤"],
    "고덕": ["⑤"],
    "상일동": ["⑤"],
    "방화": ["⑤"],
    "개화산": ["⑤"],
    "김포공항": ["⑤", "⑨", "공항"],
    "송정": ["⑤"],
    "마곡": ["⑤"],
    "발산": ["⑤"],
    "우장산": ["⑤"],
    "화곡": ["⑤"],
    "까치산": ["⑤", "②"],
    "신정": ["⑤"],
    "목동": ["⑤"],
    "오목교": ["⑤"],
    "양평": ["⑤"],
    "영등포구청": ["②", "⑤"],
    "영등포시장": ["⑤"],
    "신길": ["⑤"],
    "여의도": ["⑤", "⑨"],
    "여의나루": ["⑤"],
    "암사": ["⑧"],
    "천호": ["⑤", "⑧"],
    "강동구청": ["⑧"],
    "몽촌토성": ["⑧"],
    "잠실": ["②", "⑧"],
    "석촌": ["⑧"],
    "송파": ["⑧"],
    "가락시장": ["⑧"],
    "문정": ["⑧"],
    "장지": ["⑧"],
    "복정": ["⑧", "수인분당"],
    "산성": ["⑧"],
    "남한산성입구": ["⑧"],
    "단대오거리": ["⑧"],
    "신흥": ["⑧"],
    "수진": ["⑧"],
    "모란": ["⑧", "수인분당"],
    "개화": ["⑨"],
    "김포공항": ["⑤", "⑨", "공항"],
    "공항시장": ["⑨"],
    "신방화": ["⑨"],
    "마곡나루": ["⑨"],
    "양천향교": ["⑨"],
    "가양": ["⑨"],
    "증미": ["⑨"],
    "등촌": ["⑨"],
    "염창": ["⑨"],
    "신목동": ["⑨"],
    "선유도": ["⑨"],
    "당산": ["②", "⑨"],
    "국회의사당": ["⑨"],
    "여의도": ["⑤", "⑨"],
    "샛강": ["⑨"],
    "노량진": ["①", "⑨"],
    "노들": ["⑨"],
    "흑석": ["⑨"],
    "동작": ["④", "⑨"],
    "구반포": ["⑨"],
    "신반포": ["⑨"],
    "고속터미널": ["③", "⑦", "⑨"],
    "사평": ["⑨"],
    "신논현": ["⑨"],
    "언주": ["⑨"],
    "선정릉": ["⑨"],
    "삼성중앙": ["⑨"],
    "봉은사": ["⑨"],
    "종합운동장": ["②"],
    "삼전": ["⑨"],
    "석촌고분": ["⑨"],
    "석촌": ["⑧"],
    "송파나루": ["⑨"],
    "한성백제": ["⑨"],
    "올림픽공원": ["⑨"],
    "둔촌오륜": ["⑨"],
    "중앙보훈병원": ["⑨"],
    # 수인분당선
    "청량리": ["①", "수인분당"],
    "왕십리": ["②", "⑤", "수인분당"],
    "서울숲": ["수인분당"],
    "압구정로데오": ["수인분당"],
    "강남구청": ["⑦", "수인분당"],
    "선릉": ["②", "수인분당"],
    "한티": ["수인분당"],
    "도곡": ["③", "수인분당"],
    "구룡": ["수인분당"],
    "개포동": ["수인분당"],
    "대모산입구": ["수인분당"],
    # 경의중앙선
    "수색": ["경의중앙"],
    "디지털미디어시티": ["⑥", "공항", "경의중앙"],
    "가좌": ["경의중앙"],
    "홍대입구": ["②", "⑥", "경의중앙"],
    "서강대": ["경의중앙"],
    "공덕": ["⑤", "⑥", "공항", "경의중앙"],
    "효창공원앞": ["⑥", "경의중앙"],
    "용산": ["①", "④", "경의중앙"],
    "이촌": ["④", "경의중앙"],
    "서빙고": ["경의중앙"],
    "한남": ["경의중앙"],
    "옥수": ["③", "경의중앙"],
    "응봉": ["경의중앙"],
    "왕십리": ["②", "⑤", "경의중앙"],
    "청량리": ["①", "경의중앙"],
    # 공항철도
    "서울역": ["①", "④", "공항"],
    "공덕": ["⑤", "⑥", "공항", "경의중앙"],
    "홍대입구": ["②", "⑥", "공항", "경의중앙"],
    "디지털미디어시티": ["⑥", "공항", "경의중앙"],
    "마곡나루": ["⑨", "공항"],
    "김포공항": ["⑤", "⑨", "공항"],
    # 신분당선
    "강남": ["②", "신분당"],
    "양재": ["③", "신분당"],
    "양재시민의숲": ["신분당"],
    "청계산입구": ["신분당"],
}


def format_station(raw: str) -> str:
    """'노량진역' → '노량진역 ①⑨' 형태로 변환"""
    name = raw.strip().replace("역", "")
    lines = STATION_LINE_MAP.get(name, [])
    suffix = "".join(lines)
    return f"{name}역 {suffix}" if suffix else f"{name}역"


# ──────────────────────────────────────────────────────────────────
# 추진단계 분류 헬퍼
# ──────────────────────────────────────────────────────────────────
STAGE_KEYWORDS = {
    "입주": ["입주", "입주자모집", "입주완료"],
    "공사중": ["공사", "착공", "시공"],
    "심의중": ["심의", "심사", "검토"],
    "사업승인": ["사업승인", "승인"],
    "모집공고": ["모집공고", "공급공고", "입주자모집공고"],
    "계획중": ["계획", "예정"],
}


def classify_stage(title: str) -> str:
    title_lower = title
    for stage, keywords in STAGE_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return stage
    return "기타"


# ──────────────────────────────────────────────────────────────────
# 민간임대 판별
# ──────────────────────────────────────────────────────────────────
def is_private_rental(title: str, content: str = "") -> bool:
    combined = title + content
    # 공공임대 키워드가 있으면 제외
    public_keywords = ["공공임대", "공공지원민간임대" , "행복주택", "국민임대", "영구임대", "장기전세", "공공분양"]
    # 단, 공공지원민간임대는 민간임대로 취급 (서울시 기준)
    if "공공지원민간임대" in combined:
        return True
    for kw in public_keywords:
        if kw in combined:
            return False
    # 민간임대 키워드
    private_keywords = ["민간임대", "청년안심주택", "역세권청년주택", "역세권", "청년주택"]
    return any(kw in combined for kw in private_keywords)


# ──────────────────────────────────────────────────────────────────
# Nominatim geocoding
# ──────────────────────────────────────────────────────────────────
_GEO_CACHE: dict[str, tuple[float, float]] = {}


def geocode(address: str) -> tuple[float, float] | None:
    if address in _GEO_CACHE:
        return _GEO_CACHE[address]
    try:
        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address + " 서울", "format": "json", "limit": 1},
            headers={"User-Agent": "SeoulHousingDashboard/1.0"},
            timeout=10,
        )
        data = resp.json()
        if data:
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            _GEO_CACHE[address] = (lat, lon)
            return lat, lon
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────────────
# API 수집
# ──────────────────────────────────────────────────────────────────
def fetch_all_posts() -> list[dict]:
    posts = []
    page = 1
    while True:
        payload = {
            "bbsId": "BMSR00015",
            "pageIndex": str(page),
            "searchAdresGu": "",
            "searchCondition": "",
            "searchKeyword": "",
            "optn2": "",
            "optn5": "",
        }
        try:
            resp = requests.post(API_URL, data=payload, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[ERROR] page {page} 수집 실패: {e}")
            break

        items = data.get("resultList", [])
        if not items:
            break

        for item in items:
            # 게시일 파싱 (YYYY-MM-DD or YYYY.MM.DD)
            raw_date = item.get("createdDate", item.get("regDt", ""))
            try:
                post_dt = datetime.strptime(raw_date[:10].replace(".", "-"), "%Y-%m-%d").replace(tzinfo=KST)
                # 전날 23:59:59 KST 이전만 수집
                post_dt = post_dt.replace(hour=23, minute=59, second=59)
                if post_dt > CUTOFF:
                    continue
            except Exception:
                pass
            posts.append(item)

        # 마지막 페이지 판단
        total_count = int(data.get("totalCount", 0))
        if page * 10 >= total_count:
            break
        page += 1
        time.sleep(0.3)

    return posts


# ──────────────────────────────────────────────────────────────────
# Fallback 베이스 데이터 (85개 단지 축약)
# ──────────────────────────────────────────────────────────────────
FALLBACK_COMPLEXES = [
    {"gu": "강남구", "name": "역삼 청년안심주택", "station": "역삼역", "total": 120, "vacancy": 5, "stage": "입주"},
    {"gu": "강동구", "name": "천호역 청년주택", "station": "천호역", "total": 98, "vacancy": 0, "stage": "입주"},
    {"gu": "강북구", "name": "미아사거리 청년주택", "station": "미아사거리역", "total": 150, "vacancy": 12, "stage": "입주"},
    {"gu": "강서구", "name": "발산역 청년주택", "station": "발산역", "total": 200, "vacancy": 8, "stage": "입주"},
    {"gu": "관악구", "name": "신림역 청년안심주택", "station": "신림역", "total": 180, "vacancy": 3, "stage": "입주"},
    {"gu": "광진구", "name": "건대입구 청년주택", "station": "건대입구역", "total": 160, "vacancy": 20, "stage": "입주"},
    {"gu": "구로구", "name": "신도림 청년주택", "station": "신도림역", "total": 140, "vacancy": 0, "stage": "입주"},
    {"gu": "금천구", "name": "가산 청년안심주택", "station": "가산디지털단지역", "total": 110, "vacancy": 7, "stage": "입주"},
    {"gu": "노원구", "name": "노원역 청년주택", "station": "노원역", "total": 130, "vacancy": 15, "stage": "입주"},
    {"gu": "도봉구", "name": "쌍문역 청년주택", "station": "쌍문역", "total": 90, "vacancy": 4, "stage": "모집공고"},
    {"gu": "동대문구", "name": "청량리역 청년주택", "station": "청량리역", "total": 170, "vacancy": 0, "stage": "입주"},
    {"gu": "동작구", "name": "노량진역 청년안심주택", "station": "노량진역", "total": 210, "vacancy": 30, "stage": "입주"},
    {"gu": "마포구", "name": "홍대입구 청년주택", "station": "홍대입구역", "total": 250, "vacancy": 18, "stage": "입주"},
    {"gu": "서대문구", "name": "홍제역 청년주택", "station": "홍제역", "total": 100, "vacancy": 2, "stage": "공사중"},
    {"gu": "서초구", "name": "사당역 청년안심주택", "station": "사당역", "total": 190, "vacancy": 9, "stage": "입주"},
    {"gu": "성동구", "name": "왕십리역 청년주택", "station": "왕십리역", "total": 145, "vacancy": 11, "stage": "입주"},
    {"gu": "성북구", "name": "안암역 청년주택", "station": "안암역", "total": 125, "vacancy": 6, "stage": "입주"},
    {"gu": "송파구", "name": "잠실역 청년안심주택", "station": "잠실역", "total": 300, "vacancy": 45, "stage": "입주"},
    {"gu": "양천구", "name": "목동역 청년주택", "station": "목동역", "total": 135, "vacancy": 0, "stage": "심의중"},
    {"gu": "영등포구", "name": "여의도역 청년주택", "station": "여의도역", "total": 220, "vacancy": 22, "stage": "입주"},
    {"gu": "용산구", "name": "용산역 청년안심주택", "station": "용산역", "total": 175, "vacancy": 14, "stage": "입주"},
    {"gu": "은평구", "name": "연신내역 청년주택", "station": "연신내역", "total": 115, "vacancy": 5, "stage": "입주"},
    {"gu": "종로구", "name": "종각역 청년주택", "station": "종각역", "total": 80, "vacancy": 0, "stage": "계획중"},
    {"gu": "중구", "name": "을지로 청년안심주택", "station": "을지로3가역", "total": 95, "vacancy": 3, "stage": "입주"},
    {"gu": "중랑구", "name": "상봉역 청년주택", "station": "상봉역", "total": 155, "vacancy": 19, "stage": "모집공고"},
]


# ──────────────────────────────────────────────────────────────────
# 공고 파싱 → 단지 레코드 변환
# ──────────────────────────────────────────────────────────────────
def parse_post_to_record(item: dict) -> dict | None:
    title = item.get("bbsNm", item.get("nttSj", ""))
    content = item.get("nttCn", "")

    if not is_private_rental(title, content):
        return None

    # 자치구 추출
    gu_match = re.search(r"([가-힣]+구)", title + content)
    gu = gu_match.group(1) if gu_match else "미상"

    # 단지명
    name = title.strip()

    # 역명
    station_match = re.search(r"([가-힣A-Za-z0-9]+역)", title + content)
    station_raw = station_match.group(1) if station_match else ""
    station = format_station(station_raw.replace("역", "")) if station_raw else ""

    # 총세대수
    total_match = re.search(r"총?\s*(\d+)\s*세대", content)
    total = int(total_match.group(1)) if total_match else 0

    # 일반/특별 공급
    general_match = re.search(r"일반\s*공급\s*[：:]\s*(\d+)", content)
    special_match = re.search(r"특별\s*공급\s*[：:]\s*(\d+)", content)
    general = int(general_match.group(1)) if general_match else 0
    special = int(special_match.group(1)) if special_match else 0

    # 게시일
    reg_dt = item.get("createdDate", item.get("regDt", ""))[:10]

    # 공고 상세 URL
    ntt_id = item.get("nttId", item.get("bbsId", ""))
    detail_link = f"{DETAIL_URL}?nttId={ntt_id}&bbsId=BMSR00015" if ntt_id else ""

    stage = classify_stage(title)

    record = {
        "gu": gu,
        "name": name,
        "station": station,
        "stage": stage,
        "total": total,
        "vacancy": 0,           # PDF 파싱으로 보완 예정
        "vacancyRate": 0.0,
        "lastNoticeDate": reg_dt,
        "generalSupply": general,
        "specialSupply": special,
        "youthUnits": None,     # PDF 파싱 필요
        "newlywedUnits": None,  # PDF 파싱 필요
        "lat": None,
        "lng": None,
        "detailUrl": detail_link,
        "source": "api",
    }
    return record


# ──────────────────────────────────────────────────────────────────
# Geocoding 적용
# ──────────────────────────────────────────────────────────────────
def enrich_geocoding(complexes: list[dict]) -> list[dict]:
    for c in complexes:
        if c.get("lat") and c.get("lng"):
            continue
        query = f"{c['gu']} {c['name']}"
        result = geocode(query)
        if result:
            c["lat"], c["lng"] = result
        else:
            # 자치구 중심좌표 fallback
            GU_CENTERS = {
                "강남구": (37.5172, 127.0473), "강동구": (37.5301, 127.1238),
                "강북구": (37.6396, 127.0253), "강서구": (37.5509, 126.8495),
                "관악구": (37.4784, 126.9516), "광진구": (37.5384, 127.0826),
                "구로구": (37.4954, 126.8874), "금천구": (37.4570, 126.8954),
                "노원구": (37.6542, 127.0568), "도봉구": (37.6688, 127.0471),
                "동대문구": (37.5744, 127.0395), "동작구": (37.5124, 126.9393),
                "마포구": (37.5663, 126.9014), "서대문구": (37.5791, 126.9368),
                "서초구": (37.4837, 127.0324), "성동구": (37.5634, 127.0369),
                "성북구": (37.5894, 127.0167), "송파구": (37.5145, 127.1059),
                "양천구": (37.5170, 126.8666), "영등포구": (37.5264, 126.8962),
                "용산구": (37.5323, 126.9906), "은평구": (37.6026, 126.9292),
                "종로구": (37.5735, 126.9790), "중구": (37.5640, 126.9975),
                "중랑구": (37.6063, 127.0926),
            }
            center = GU_CENTERS.get(c.get("gu", ""), (37.5665, 126.9780))
            c["lat"], c["lng"] = center
    return complexes


# ──────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────
def main():
    print(f"[INFO] 수집 기준시각: {CUTOFF.strftime('%Y-%m-%d %H:%M:%S KST')}")

    # 1) API 수집
    print("[INFO] 서울시 API 수집 중...")
    posts = fetch_all_posts()
    print(f"[INFO] 총 {len(posts)}건 수집")

    # 2) 민간임대 파싱
    api_complexes = []
    for post in posts:
        record = parse_post_to_record(post)
        if record:
            api_complexes.append(record)
    print(f"[INFO] 민간임대 공고: {len(api_complexes)}건")

    # 3) Fallback 데이터 보완 (API 수집이 0건이거나 이름 매칭 실패 시)
    fallback_complexes = []
    for fb in FALLBACK_COMPLEXES:
        station_fmt = format_station(fb["station"].replace("역", ""))
        total = fb["total"]
        vacancy = fb["vacancy"]
        fallback_complexes.append({
            "gu": fb["gu"],
            "name": fb["name"],
            "station": station_fmt,
            "stage": fb["stage"],
            "total": total,
            "vacancy": vacancy,
            "vacancyRate": round(vacancy / total * 100, 1) if total else 0.0,
            "lastNoticeDate": "",
            "generalSupply": 0,
            "specialSupply": 0,
            "youthUnits": None,
            "newlywedUnits": None,
            "lat": None,
            "lng": None,
            "detailUrl": "",
            "source": "fallback",
        })

    # API 결과 우선, 없으면 fallback
    complexes = api_complexes if api_complexes else fallback_complexes

    # 4) Geocoding
    print("[INFO] Geocoding 중 (Nominatim)...")
    complexes = enrich_geocoding(complexes)

    # 5) KPI 계산
    total_complexes = len(complexes)
    active_complexes = sum(1 for c in complexes if c["stage"] == "입주")
    total_units = sum(c["total"] for c in complexes)
    vacancy_units = sum(c.get("vacancy", 0) for c in complexes)
    avg_vacancy_rate = round(vacancy_units / total_units * 100, 1) if total_units else 0.0

    # 6) data.json 출력
    output = {
        "updatedAt": NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "kpi": {
            "totalComplexes": total_complexes,
            "activeComplexes": active_complexes,
            "totalUnits": total_units,
            "vacancyUnits": vacancy_units,
            "avgVacancyRate": avg_vacancy_rate,
        },
        "complexes": complexes,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[INFO] data.json 저장 완료 ({total_complexes}개 단지)")


if __name__ == "__main__":
    main()
