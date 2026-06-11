"""
fetch.py — 서울시 청년안심주택 공고 수집 + data.json 생성
구조:
  - pdf/complexes-seoul-si.pdf → 135개 전체 사업장 마스터 (지도 표시용)
  - BASE_DATA            → 현재 임대운영 85개 상세 데이터 (테이블 표시용)
  - 서울시 API           → 공고 매칭 (임대운영 단지 대상)
  - tableVisible: true   → BASE_DATA 단지 (테이블+지도)
  - tableVisible: false  → PDF 전용 단지 (지도만, 회색 마커)
"""

import json, re, time, requests, os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
NOW_KST = datetime.now(KST)
CUTOFF_DATE = (NOW_KST - timedelta(days=1)).strftime('%Y-%m-%d')

API_URL    = "https://soco.seoul.go.kr/youth/pgm/home/yohome/bbsListJson.json"
DETAIL_BASE = "https://soco.seoul.go.kr/youth/bbs/BMSR00015/view.do"
OUTPUT_PATH = "data.json"
PDF_PATH    = "pdf/complexes-seoul-si.pdf"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://soco.seoul.go.kr/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# ── 역명→호선 매핑 ────────────────────────────────────────────────
STATION_LINE_MAP = {
    "서울역":["①","④","공항"],"시청":["①","②"],"종각":["①"],"종로3가":["①","③","⑤"],
    "동대문":["①","④"],"청량리":["①","수인분당"],"신도림":["①","②"],"노량진":["①","⑨"],
    "용산":["①","④"],"남영":["①"],"대방":["①"],"구로":["①"],
    "합정":["②","⑥"],"홍대입구":["②","⑥","공항","경의중앙"],"신촌":["②"],"이대":["②"],
    "아현":["②"],"충정로":["②","⑤"],"강변":["②"],"구의":["②"],"건대입구":["②","⑦"],
    "성수":["②"],"왕십리":["②","⑤","수인분당","경의중앙"],"한양대":["②"],
    "잠실새내":["②"],"잠실":["②","⑧"],"종합운동장":["②"],"삼성":["②"],
    "선릉":["②","수인분당"],"역삼":["②"],"강남":["②","신분당"],"교대":["②","③"],
    "서초":["②"],"방배":["②"],"사당":["②","④"],"낙성대":["②"],
    "서울대입구":["②"],"봉천":["②"],"신림":["②"],"구로디지털단지":["②"],
    "대림":["②","⑦"],"문래":["②"],"영등포구청":["②","⑤"],"당산":["②","⑨"],
    "을지로3가":["②","③"],"을지로4가":["②","⑤"],"신당":["②","⑥"],
    "동대문역사문화공원":["②","④","⑤"],"뚝섬":["②"],
    "경복궁":["③"],"안국":["③"],"충무로":["③","④"],"동대입구":["③"],
    "약수":["③","⑥"],"금호":["③"],"옥수":["③","경의중앙"],"압구정":["③"],
    "신사":["③"],"잠원":["③"],"고속터미널":["③","⑦","⑨"],
    "남태령":["④"],"홍제":["③","⑥"],"불광":["③","⑥"],"녹번":["③"],"무악재":["③"],
    "독립문":["③"],"동묘앞":["①","⑥"],
    "이촌":["④","경의중앙"],"신용산":["④"],"삼각지":["④","⑥"],
    "숙대입구":["④"],"명동":["④"],"회현":["④"],"동작":["④","⑨"],
    "이수":["④","⑦"],"총신대입구":["④","⑦"],
    "미아사거리":["④"],"미아":["④"],"수유":["④"],"쌍문":["④"],"창동":["①","④"],
    "공덕":["⑤","⑥","공항","경의중앙"],"애오개":["⑤"],"서대문":["⑤"],
    "광화문":["⑤"],"여의도":["⑤","⑨"],"여의나루":["⑤"],"마포":["⑤"],
    "군자":["⑤","⑦"],"아차산":["⑤"],"광나루":["⑤"],"천호":["⑤","⑧"],
    "강동":["⑤","⑧"],"길동":["⑤"],"명일":["⑤"],"고덕":["⑤"],
    "방화":["⑤"],"김포공항":["⑤","⑨","공항"],"마곡":["⑤"],"발산":["⑤"],
    "우장산":["⑤"],"화곡":["⑤"],"까치산":["⑤"],"목동":["⑤"],"오목교":["⑤"],
    "양평":["⑤"],"영등포시장":["⑤"],"신길":["⑤"],
    "연신내":["③","⑥"],"구산":["⑥"],"응암":["⑥"],"역촌":["⑥"],"새절":["⑥"],
    "증산":["⑥"],"디지털미디어시티":["⑥","공항","경의중앙"],"망원":["⑥"],
    "마포구청":["⑥"],"상수":["⑥"],"광흥창":["⑥"],"대흥":["⑥"],
    "효창공원앞":["⑥"],"녹사평":["⑥"],"이태원":["⑥"],"한강진":["⑥"],
    "버티고개":["⑥"],"청구":["⑤","⑥"],"보문":["⑥"],"안암":["⑥"],
    "고려대":["⑥"],"월곡":["⑥"],"상월곡":["⑥"],"돌곶이":["⑥"],
    "화랑대":["⑥"],"봉화산":["⑥"],"신내":["⑥"],"석계":["①","⑥"],
    "수락산":["⑦"],"중계":["⑦"],"하계":["⑦"],"공릉":["⑦"],
    "태릉입구":["⑦"],"먹골":["⑦"],"중화":["⑦"],"상봉":["⑦"],
    "면목":["⑦"],"사가정":["⑦"],"용마산":["⑦"],"중곡":["⑦"],
    "어린이대공원":["⑦"],"뚝섬유원지":["⑦"],"청담":["⑦"],
    "강남구청":["⑦","수인분당"],"학동":["⑦"],"논현":["⑦"],"반포":["⑦"],
    "내방":["⑦"],"남성":["⑦"],"숭실대입구":["⑦"],"상도":["⑦"],
    "장승배기":["⑦"],"신대방삼거리":["⑦"],"보라매":["⑦"],"신풍":["⑦"],
    "노원":["④","⑦"],
    "암사":["⑧"],"강동구청":["⑧"],"몽촌토성":["⑧"],"석촌":["⑧"],
    "송파":["⑧"],"가락시장":["⑧"],"문정":["⑧"],"장지":["⑧"],
    "개화":["⑨"],"공항시장":["⑨"],"신방화":["⑨"],"마곡나루":["⑨","공항"],
    "양천향교":["⑨"],"가양":["⑨"],"증미":["⑨"],"등촌":["⑨"],
    "염창":["⑨"],"신목동":["⑨"],"선유도":["⑨"],"국회의사당":["⑨"],
    "샛강":["⑨"],"노들":["⑨"],"흑석":["⑨"],"구반포":["⑨"],
    "신반포":["⑨"],"사평":["⑨"],"신논현":["⑨"],"언주":["⑨"],
    "선정릉":["⑨"],"삼성중앙":["⑨"],"봉은사":["⑨"],"삼전":["⑨"],
    "석촌고분":["⑨"],"송파나루":["⑨"],"한성백제":["⑨"],
    "올림픽공원":["⑨"],"둔촌오륜":["⑨"],"중앙보훈병원":["⑨"],
    "서울숲":["수인분당"],"압구정로데오":["수인분당"],"한티":["수인분당"],
    "도곡":["③","수인분당"],"구룡":["수인분당"],"개포동":["수인분당"],
    "대모산입구":["수인분당"],"복정":["⑧","수인분당"],
    "수색":["경의중앙"],"가좌":["경의중앙"],"서강대":["경의중앙"],
    "서빙고":["경의중앙"],"한남":["경의중앙"],"응봉":["경의중앙"],
    "양재":["③","신분당"],"양재시민의숲":["신분당"],
    "개봉":["①"],"광운대":["①"],
    "마장":["⑤"],"서울대벤처타운":["신림"],
    "서울":["①","④","공항"],"장한평":["⑤"],
    "화계":["④"],"회기":["①","경의중앙"],
    "솔밭공원":["우이신설"],
    "가산디지털단지":["①","⑦"],
    "신설동":["①","②"],
    "독산":["①"],"시흥사거리":["①"],
    "대림삼거리":["⑦"],"온수":["①","⑦"],"천왕":["⑦"],
    "남부터미널":["③"],"상왕십리":["②","수인분당"],
    "답십리":["⑤"],
    "봉천":["②"],"송정":["공항"],
    "청량리":["①","수인분당"],
    # 미개통 예정역
    "도림사거리":[],"숭곡초교":[],"종암경찰서":[],"서림":[],"동북선":[],
}

PENDING_STATIONS = {"도림사거리","숭곡초교","종암경찰서","서림","동북선"}

# ── 역 좌표 fallback ──────────────────────────────────────────────
STATION_COORDS = {
    "서울역":(37.5547,126.9706),"서울":(37.5547,126.9706),
    "남영":(37.5452,126.9709),"용산":(37.5302,126.9651),
    "노량진":(37.5138,126.9421),"대방":(37.5145,126.9320),
    "개봉":(37.4937,126.8631),"광운대":(37.6244,127.0578),
    "회기":(37.5890,127.0473),"청량리":(37.5836,127.0457),
    "독산":(37.4698,126.8962),"시흥사거리":(37.4543,126.8983),
    "신설동":(37.5733,127.0246),
    "충정로":(37.5556,126.9647),"합정":(37.5494,126.9148),
    "홍대입구":(37.5571,126.9241),"강변":(37.5346,127.0953),
    "구의":(37.5392,127.0844),"건대입구":(37.5401,127.0703),
    "왕십리":(37.5615,127.0374),"잠실새내":(37.5103,127.0831),
    "잠실":(37.5133,127.1001),"선릉":(37.5046,127.0491),
    "역삼":(37.5007,127.0363),"강남":(37.4979,127.0276),
    "교대":(37.4934,127.0138),"서초":(37.4836,127.0097),
    "방배":(37.4813,127.0051),"사당":(37.4766,126.9815),
    "서울대입구":(37.4813,126.9527),"봉천":(37.4818,126.9472),
    "신림":(37.4849,126.9292),"구로디지털단지":(37.4852,126.9012),
    "대림":(37.4918,126.8958),"영등포구청":(37.5260,126.8961),
    "당산":(37.5337,126.9013),"신당":(37.5641,127.0117),
    "동대문역사문화공원":(37.5648,127.0094),"성수":(37.5444,127.0563),
    "상왕십리":(37.5652,127.0298),
    "불광":(37.6101,126.9292),"연신내":(37.6194,126.9196),
    "구산":(37.6257,126.9147),"증산":(37.5823,126.9163),
    "동묘앞":(37.5721,127.0133),"양재":(37.4845,127.0340),
    "남부터미널":(37.4855,127.0138),
    "삼각지":(37.5346,126.9731),"숙대입구":(37.5415,126.9742),
    "명동":(37.5609,126.9861),"회현":(37.5582,126.9779),
    "동작":(37.4993,126.9814),"이수":(37.4856,126.9807),
    "총신대입구":(37.4836,126.9816),"미아사거리":(37.6141,127.0294),
    "쌍문":(37.6485,127.0468),"창동":(37.6522,127.0468),
    "수유":(37.6375,127.0251),"노원":(37.6555,127.0561),
    "화계":(37.6407,127.0173),
    "공덕":(37.5449,126.9513),"마포":(37.5483,126.9494),
    "여의도":(37.5215,126.9243),"군자":(37.5555,127.0780),
    "아차산":(37.5566,127.0894),"천호":(37.5381,127.1240),
    "강동":(37.5304,127.1266),"길동":(37.5280,127.1391),
    "발산":(37.5582,126.8390),"우장산":(37.5564,126.8505),
    "화곡":(37.5490,126.8535),"목동":(37.5256,126.8749),
    "신길":(37.5167,126.9207),"장한평":(37.5680,127.0503),
    "마장":(37.5676,127.0432),"답십리":(37.5720,127.0589),
    "망원":(37.5558,126.9072),"마포구청":(37.5524,126.9090),
    "상수":(37.5482,126.9249),"광흥창":(37.5464,126.9327),
    "대흥":(37.5418,126.9428),"효창공원앞":(37.5393,126.9612),
    "이태원":(37.5344,126.9946),"보문":(37.5895,127.0193),
    "안암":(37.5866,127.0254),"고려대":(37.5898,127.0328),
    "월곡":(37.5993,127.0438),"돌곶이":(37.6029,127.0548),
    "화랑대":(37.6088,127.0641),
    "수락산":(37.6688,127.0648),"중계":(37.6560,127.0681),
    "공릉":(37.6375,127.0740),"태릉입구":(37.6255,127.0742),
    "먹골":(37.6029,127.0900),"상봉":(37.5875,127.0854),
    "중곡":(37.5682,127.0772),"어린이대공원":(37.5485,127.0811),
    "뚝섬유원지":(37.5367,127.0700),"청담":(37.5232,127.0558),
    "강남구청":(37.5178,127.0424),"학동":(37.5168,127.0264),
    "논현":(37.5117,127.0226),"반포":(37.5046,127.0127),
    "내방":(37.4942,126.9985),"남성":(37.4860,126.9926),
    "숭실대입구":(37.4950,126.9653),"상도":(37.4994,126.9524),
    "장승배기":(37.5071,126.9412),"신대방삼거리":(37.5085,126.9226),
    "보라매":(37.4967,126.9219),"신풍":(37.5137,126.9075),
    "온수":(37.4890,126.8208),"천왕":(37.4948,126.8348),
    "대림삼거리":(37.4920,126.8843),
    "강동구청":(37.5330,127.1235),"몽촌토성":(37.5152,127.1220),
    "문정":(37.4863,127.1197),"장지":(37.4779,127.1256),
    "김포공항":(37.5633,126.8009),"마곡나루":(37.5689,126.8131),
    "가양":(37.5620,126.8526),"증미":(37.5506,126.8673),
    "등촌":(37.5423,126.8705),"염창":(37.5375,126.8810),
    "선유도":(37.5274,126.8983),"국회의사당":(37.5290,126.9154),
    "신논현":(37.5044,127.0253),"언주":(37.5121,127.0387),
    "선정릉":(37.5046,127.0497),"삼성중앙":(37.5087,127.0574),
    "봉은사":(37.5141,127.0631),"삼전":(37.5018,127.0896),
    "한성백제":(37.5065,127.1081),"올림픽공원":(37.5110,127.1188),
    "서울숲":(37.5466,127.0445),"압구정로데오":(37.5268,127.0394),
    "한티":(37.4918,127.0547),"도곡":(37.4882,127.0431),
    "가좌":(37.5747,126.9017),"서강대":(37.5512,126.9378),
    "서울대벤처타운":(37.4752,126.9536),"서림":(37.4840,126.9329),
    "숭곡초교":(37.6021,127.0373),"종암경찰서":(37.5947,127.0168),
    "동북선":(37.6000,127.0200),
    "솔밭공원":(37.6519,127.0360),
    "도림사거리":(37.5112,126.9167),
    "가산디지털단지":(37.4774,126.8826),
    "송정":(37.5627,126.8028),
    "신설동":(37.5733,127.0246),
}


def format_station(raw: str) -> str:
    name = re.sub(r'역$', '', raw.strip())
    name = re.sub(r'\(.*?\)', '', name).strip()
    if name in PENDING_STATIONS:
        return f"{name}역 (예정)"
    lines = STATION_LINE_MAP.get(name, [])
    suffix = "".join(lines)
    return f"{name}역 {suffix}".strip() if suffix else f"{name}역"


# ── PDF 파싱 (extract_tables 사용) ────────────────────────────────
STAGE_KEYWORDS = ['인가완료', '착공신고', '착공전', '준공', '입주']

def _safe_int(v) -> int:
    if not v: return 0
    try: return int(str(v).replace(',','').strip())
    except: return 0

def _is_valid_station(name: str) -> bool:
    """역명으로 유효한지 확인"""
    clean = re.sub(r'\(.*?\)', '', name).strip()
    clean = re.sub(r'역$', '', clean)
    return (clean in STATION_LINE_MAP or
            clean in PENDING_STATIONS or
            name.endswith('역'))

def parse_pdf_complexes(pdf_path: str) -> list:
    try:
        import pdfplumber
    except ImportError:
        print("[WARN] pdfplumber 미설치. PDF 파싱 건너뜀.")
        return []

    all_rows = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    all_rows.extend(tables[0])
    except Exception as e:
        print(f"[WARN] PDF 읽기 실패: {e}")
        return []

    results = []
    for row in all_rows:
        if len(row) < 12:
            continue
        station_raw = (row[3] or '').strip()
        stage_raw   = (row[11] or '').strip()
        gu          = (row[1] or '').strip()

        # 헤더 행 제외
        if not station_raw or not stage_raw or not gu:
            continue
        if station_raw == '지하철역' or gu == '자치구':
            continue

        # 추진단계 정규화
        stage = next((s for s in STAGE_KEYWORDS if s in stage_raw), None)
        if not stage:
            continue

        # 역명 정규화: 역 suffix 없으면 추가 (단, 유효한 역명일 때만)
        station = station_raw
        if not station.endswith('역'):
            if '예정' in station:
                station = station + '역' if not station.endswith('역') else station
            elif _is_valid_station(station):
                station = station + '역'
            else:
                # 역명이 아닌 경우 (e.g. "간선도로변") → 역 없이 유지
                print(f"[WARN] 유효하지 않은 역명: '{station}' (gu={gu}) — 주소 기반 geocoding 사용")
                station = None

        results.append({
            'pdfId':        int(row[0]) if row[0] and str(row[0]).strip().isdigit() else None,
            'gu':           gu,
            'address':      (row[2] or '').strip(),
            'subway':       station,
            'total':        _safe_int(row[7]),
            'public':       _safe_int(row[8]),
            'private':      _safe_int(row[9]),
            'stage':        stage,
            'approval':     (row[12] or '').strip() or None,
            'construction': (row[13] or '').strip() or None,
            'completion':   (row[14] or '').strip() or None,
            'moveIn':       (row[15] or '').strip() or None,
        })

    print(f"[INFO] PDF에서 {len(results)}개 단지 파싱됨")
    return results


# 역명 별칭 (PDF와 BASE_DATA 간 표기 차이 보정)
STATION_ALIASES = {
    "서림":         "서울대벤처타운",
    "서울대벤처타운": "서림",
    "동북선":       "종암경찰서",
    "종암경찰서":   "동북선",
}

def find_base_match(pdf_row: dict, base_list: list, exclude_ids: set | None = None) -> dict | None:
    """PDF 단지를 BASE_DATA에서 (구+역+민간세대수)로 매칭"""
    gu      = pdf_row['gu']
    station = re.sub(r'역$', '', pdf_row['subway'] or '')
    station = re.sub(r'\(.*?\)', '', station).strip()  # "(예정)" 등 제거
    station_alias = STATION_ALIASES.get(station)
    private = pdf_row['private']
    best, best_diff = None, 999
    for b in base_list:
        if exclude_ids and b['id'] in exclude_ids:
            continue
        if b['gu'] != gu:
            continue
        b_station = re.sub(r'역$', '', b.get('subway',''))
        b_station = re.sub(r'\(.*?\)', '', b_station).strip()
        if b_station != station and b_station != station_alias:
            continue
        diff = abs((b.get('private') or 0) - private)
        if diff <= 3 and diff < best_diff:
            best, best_diff = b, diff
    return best


# ── BASE_DATA (85개 임대운영 단지) ────────────────────────────────
BASE_DATA = [{"id":1,"gu":"용산구","name":"용산베르디움프렌즈","subway":"삼각지역","stage":"입주","total":1226,"public":421,"private":805,"area":8671.1,"vacancy":0.0,"special":0,"general":0,"moveIn":"2021-02-15","lastNotice":"2020-09-29","approval":"2017-03-09","construction":"2017-12-11","completion":"2021-02-01","operator":"(주)용산대한뉴스테이위탁관리부동산투자회사","note":""},{"id":2,"gu":"서대문구","name":"어바니엘 충정로","subway":"충정로역","stage":"입주","total":499,"public":49,"private":450,"area":5412.3,"vacancy":0.0,"special":0,"general":0,"moveIn":"2020-02-28","lastNotice":"2019-08-29","approval":"2017-03-30","construction":"2017-06-29","completion":"2020-01-17","operator":"원석디앤씨","note":"최초"},{"id":3,"gu":"마포구","name":"서교동 효성해링턴타워","subway":"합정역","stage":"입주","total":1121,"public":199,"private":922,"area":6735.9,"vacancy":0.0,"special":0,"general":0,"moveIn":"2020-05-01","lastNotice":"2019-11-05","approval":"2017-03-30","construction":"2017-08-02","completion":"2020-04-23","operator":"멀티에셋합정역청년주택전문투자형사모투자(유)","note":"최초"},{"id":4,"gu":"강서구","name":"우장산역 해링턴 타워","subway":"우장산역","stage":"입주","total":533,"public":87,"private":446,"area":5790.3,"vacancy":0.0044843,"special":1,"general":1,"moveIn":"2021-09-10","lastNotice":"2025-10-02","approval":"2017-09-21","construction":"2018-12-20","completion":"2021-09-03","operator":"주식회사 선우","note":""},{"id":5,"gu":"마포구","name":"이랜드 PEER 신촌","subway":"광흥창역","stage":"입주","total":681,"public":120,"private":561,"area":5232.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2021-02-19","lastNotice":"2020-09-11","approval":"2017-12-07","construction":"2018-06-11","completion":"2021-01-11","operator":"(주)이베데스다제일호위탁관리부동산투자회사","note":"최초"},{"id":6,"gu":"성동구","name":"힐데스하임","subway":"장한평역","stage":"입주","total":170,"public":22,"private":148,"area":682.8,"vacancy":0.02027,"special":0,"general":3,"moveIn":"2020-04-06","lastNotice":"2026-01-08","approval":"2017-11-15","construction":"2018-04-04","completion":"2020-03-02","operator":"유(U)삼진랜드","note":""},{"id":7,"gu":"강남구","name":"리스트 강남","subway":"신논현역","stage":"입주","total":345,"public":86,"private":259,"area":1556.3,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-04-11","lastNotice":"2022-02-09","approval":"2018-12-19","construction":"2019-07-09","completion":"2022-04-06","operator":"(주)브이홀딩스","note":"최초"},{"id":8,"gu":"강남구","name":"선정릉역 모아엘가 퍼스트 홈","subway":"선정릉역","stage":"입주","total":298,"public":38,"private":260,"area":2213.2,"vacancy":0.0,"special":0,"general":0,"moveIn":"2023-04-05","lastNotice":"2023-02-10","approval":"2018-10-11","construction":"2019-11-07","completion":"2023-01-13","operator":"(주)삼조디앤씨","note":"최초"},{"id":9,"gu":"광진구","name":"옥산그린타워","subway":"강변역","stage":"입주","total":84,"public":18,"private":66,"area":659.1,"vacancy":0.0,"special":0,"general":0,"moveIn":"2020-04-06","lastNotice":None,"approval":"2018-05-28","construction":"2018-11-09","completion":"2020-04-06","operator":"","note":""},{"id":10,"gu":"도봉구","name":"인히어 쌍문","subway":"쌍문역","stage":"입주","total":288,"public":70,"private":218,"area":1546.4,"vacancy":0.050459,"special":4,"general":7,"moveIn":"2022-03-07","lastNotice":"2026-01-29","approval":"2017-12-18","construction":"2019-08-30","completion":"2022-02-04","operator":"(주)케이티엔지","note":""},{"id":11,"gu":"관악구","name":"최강타워","subway":"신림역","stage":"입주","total":338,"public":79,"private":259,"area":2962.6,"vacancy":0.007722,"special":0,"general":2,"moveIn":"2023-07-10","lastNotice":"2026-01-22","approval":"2019-08-29","construction":"2020-06-18","completion":"2023-05-30","operator":"(주)신림리더스하우징","note":""},{"id":12,"gu":"강서구","name":"센터스퀘어 등촌","subway":"등촌역","stage":"입주","total":520,"public":49,"private":471,"area":4425.7,"vacancy":0.0,"special":0,"general":0,"moveIn":"2021-01-30","lastNotice":"2020-08-03","approval":"2018-04-04","construction":"2018-07-05","completion":"2020-12-30","operator":"멀티에셋등촌역청년주택전문투자형사모부동산투자(유)","note":""},{"id":13,"gu":"송파구","name":"잠실엘타워","subway":"잠실새내역","stage":"입주","total":298,"public":88,"private":210,"area":1960.9,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-07-27","lastNotice":"2022-06-28","approval":"2018-11-23","construction":"2020-02-10","completion":"2022-10-13","operator":"금강실업","note":""},{"id":14,"gu":"강서구","name":"아임2030 등촌역","subway":"등촌역","stage":"입주","total":285,"public":19,"private":266,"area":1322.7,"vacancy":0.003759,"special":1,"general":0,"moveIn":"2020-06-02","lastNotice":"2025-08-13","approval":"2018-05-09","construction":"2018-08-10","completion":"2020-05-01","operator":"대호주택건설(김성수)","note":""},{"id":15,"gu":"서초구","name":"코네스트(CONEST)","subway":"양재역","stage":"입주","total":411,"public":122,"private":289,"area":2805.1,"vacancy":0.013841,"special":2,"general":2,"moveIn":"2023-06-24","lastNotice":"2025-12-18","approval":"2019-12-12","construction":"2020-05-06","completion":"2023-06-12","operator":"당당 대표자 장요섭 외 2인","note":""},{"id":16,"gu":"강동구","name":"천호역 효성해팅턴타워","subway":"천호역","stage":"입주","total":900,"public":264,"private":636,"area":5893.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2023-08-10","lastNotice":"2025-06-11","approval":"2018-07-26","construction":"2020-04-03","completion":"2023-07-24","operator":"(주)이지스청년주택제1호위탁관리부동산투자회사","note":"예비"},{"id":17,"gu":"영등포구","name":"포레나 당산","subway":"영등포구청역","stage":"입주","total":624,"public":131,"private":493,"area":6316.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-12-20","lastNotice":"2026-01-22","approval":"2018-08-31","construction":"2020-04-24","completion":"2022-12-01","operator":"(주)당산동청년주택피에프브이","note":"예비"},{"id":18,"gu":"용산구","name":"용산원효 루미니","subway":"남영역","stage":"입주","total":812,"public":333,"private":479,"area":5571.2,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-05-01","lastNotice":"2022-02-11","approval":"2018-10-11","construction":"2019-02-07","completion":"2022-04-28","operator":"(주)롯데건설","note":""},{"id":19,"gu":"강남구","name":"삼성동 마에스트로","subway":"선릉역","stage":"입주","total":299,"public":82,"private":217,"area":1578.3,"vacancy":0.036866,"special":0,"general":8,"moveIn":"2023-09-15","lastNotice":"2025-10-23","approval":"2019-03-19","construction":"2021-03-15","completion":"2023-07-31","operator":"선릉역마에스트로역세권청년주택프로젝트금융투자 주식회사","note":""},{"id":20,"gu":"동작구","name":"더클래식 동작","subway":"노량진역","stage":"입주","total":272,"public":37,"private":235,"area":923.0,"vacancy":0.025532,"special":2,"general":4,"moveIn":"2020-10-30","lastNotice":"2026-01-08","approval":"2018-05-23","construction":"2018-10-12","completion":"2020-11-17","operator":"조한문 외 9인","note":""},{"id":21,"gu":"중랑구","name":"칼튼테라스","subway":"먹골역","stage":"입주","total":235,"public":24,"private":211,"area":1978.2,"vacancy":0.014218,"special":0,"general":3,"moveIn":"2021-12-27","lastNotice":"2025-07-02","approval":"2018-09-14","construction":"2019-08-06","completion":"2021-11-01","operator":"주식회사 더블라썸묵동","note":""},{"id":23,"gu":"서초구","name":"서초꽃마을 주얼리","subway":"서초역","stage":"입주","total":280,"public":68,"private":212,"area":2557.9,"vacancy":0.009434,"special":0,"general":2,"moveIn":"2021-04-01","lastNotice":"2026-01-15","approval":"2019-01-04","construction":"2019-06-25","completion":"2021-03-23","operator":"서초꽃마을 주얼리 황인 외 3명","note":""},{"id":24,"gu":"강동구","name":"천호한강청년주택","subway":"천호역","stage":"입주","total":225,"public":50,"private":175,"area":1358.0,"vacancy":0.017143,"special":1,"general":2,"moveIn":"2021-08-26","lastNotice":"2026-01-29","approval":"2019-02-28","construction":"2019-07-24","completion":"2021-08-20","operator":"㈜알이비에셋","note":""},{"id":25,"gu":"노원구","name":"와이엔타워","subway":"태릉입구역","stage":"입주","total":270,"public":75,"private":195,"area":1456.7,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-01-02","lastNotice":"2025-11-06","approval":"2019-08-12","construction":"2019-12-10","completion":"2021-12-02","operator":"태운산업개발㈜","note":"예비"},{"id":26,"gu":"동대문구","name":"휘경제이스카이시티","subway":"회기역","stage":"입주","total":99,"public":9,"private":90,"area":919.0,"vacancy":0.055556,"special":1,"general":4,"moveIn":"2021-02-15","lastNotice":"2026-01-22","approval":"2019-05-09","construction":"2019-05-16","completion":"2021-01-21","operator":"주식회사 휴먼타운","note":""},{"id":27,"gu":"강서구","name":"보눔하우스 화곡","subway":"화곡역","stage":"입주","total":57,"public":9,"private":48,"area":573.5,"vacancy":0.083333,"special":0,"general":4,"moveIn":"2021-01-10","lastNotice":"2025-12-11","approval":"2019-04-22","construction":"2019-06-28","completion":"2021-03-24","operator":"보눔하우스 화곡 대표 장의종","note":""},{"id":28,"gu":"광진구","name":"비바힐스 강변","subway":"강변역","stage":"입주","total":98,"public":28,"private":70,"area":916.2,"vacancy":0.014286,"special":1,"general":0,"moveIn":"2021-12-03","lastNotice":"2026-02-05","approval":"2019-10-30","construction":"2020-04-14","completion":"2021-11-10","operator":"정지량 외 6명","note":""},{"id":30,"gu":"관악구","name":"BX201","subway":"서울대입구역","stage":"입주","total":201,"public":31,"private":170,"area":815.2,"vacancy":0.011765,"special":0,"general":2,"moveIn":"2022-05-14","lastNotice":"2026-01-29","approval":"2019-11-29","construction":"2020-05-27","completion":"2022-05-11","operator":"박정호 외 3인","note":""},{"id":31,"gu":"종로구","name":"숭인동 동대문 영하우스","subway":"동묘앞역","stage":"입주","total":238,"public":31,"private":207,"area":855.0,"vacancy":0.048309,"special":3,"general":7,"moveIn":"2020-05-21","lastNotice":"2025-03-31","approval":None,"construction":None,"completion":"2020-05-21","operator":"(주)포씨즈","note":""},{"id":32,"gu":"영등포구","name":"도림브라보","subway":"도림사거리역","stage":"입주","total":99,"public":18,"private":81,"area":680.8,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-01-10","lastNotice":"2021-12-20","approval":"2019-09-10","construction":"2019-11-01","completion":"2021-11-26","operator":"김병준","note":"최초"},{"id":33,"gu":"도봉구","name":"에드가 쌍문","subway":"솔밭공원역","stage":"입주","total":253,"public":48,"private":205,"area":3110.0,"vacancy":0.673171,"special":13,"general":125,"moveIn":"2022-07-25","lastNotice":"2023-01-27","approval":"2019-05-23","construction":"2020-04-22","completion":"2022-05-13","operator":"(주)도휘","note":""},{"id":34,"gu":"서대문구","name":"스타타워","subway":"가좌역","stage":"입주","total":124,"public":15,"private":109,"area":689.0,"vacancy":0.055046,"special":0,"general":6,"moveIn":"2022-12-17","lastNotice":"2025-12-18","approval":"2019-10-04","construction":"2020-09-19","completion":"2022-12-09","operator":"최병덕 외 10인(가자자산)","note":""},{"id":35,"gu":"동작구","name":"더써밋타워","subway":"노량진역","stage":"입주","total":299,"public":40,"private":259,"area":1335.4,"vacancy":0.023166,"special":1,"general":5,"moveIn":"2024-04-16","lastNotice":"2026-01-29","approval":"2020-03-24","construction":"2021-09-01","completion":"2024-03-29","operator":"코레이트노량진역청년주택전문투자형사모부동산투자 유한회사","note":""},{"id":36,"gu":"광진구","name":"센텀힐스한강","subway":"강변역","stage":"입주","total":70,"public":18,"private":52,"area":648.0,"vacancy":0.057692,"special":0,"general":3,"moveIn":"2023-04-24","lastNotice":"2025-10-30","approval":"2020-04-14","construction":"2021-09-27","completion":"2023-04-11","operator":"양석영, 이상문","note":""},{"id":37,"gu":"은평구","name":"호반베르디움 스테이원","subway":"불광역","stage":"입주","total":977,"public":347,"private":630,"area":8661.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-12-26","lastNotice":"2022-08-12","approval":"2019-08-29","construction":"2020-03-06","completion":"2022-12-29","operator":"(주)대조피에프브이","note":"최초"},{"id":38,"gu":"강서구","name":"엘크루 발산","subway":"발산역","stage":"입주","total":252,"public":53,"private":199,"area":1785.4,"vacancy":0.065327,"special":0,"general":13,"moveIn":"2022-01-15","lastNotice":"2025-12-04","approval":"2019-10-29","construction":"2020-02-07","completion":"2022-01-10","operator":"윤석표 외 2인","note":""},{"id":39,"gu":"광진구","name":"리마크빌 군자","subway":"군자역","stage":"입주","total":299,"public":84,"private":215,"area":1651.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2022-10-04","lastNotice":"2022-07-13","approval":"2020-01-06","construction":"2020-07-31","completion":"2022-08-30","operator":"(주)케이리얼티임대주택제3호위탁관리부동산투자회사","note":"최초"},{"id":40,"gu":"송파구","name":"잠실센트럴파크","subway":"잠실역","stage":"입주","total":217,"public":71,"private":146,"area":1279.6,"vacancy":0.280822,"special":1,"general":40,"moveIn":"2023-09-18","lastNotice":"2024-02-22","approval":"2020-04-08","construction":"2021-01-29","completion":"2023-08-02","operator":"허남이","note":""},{"id":41,"gu":"동대문구","name":"회기역 하트리움","subway":"회기역","stage":"입주","total":582,"public":80,"private":502,"area":5663.0,"vacancy":0.007968,"special":0,"general":4,"moveIn":"2023-01-28","lastNotice":"2026-02-05","approval":"2019-10-17","construction":"2020-04-22","completion":"2023-01-20","operator":"(주)두진","note":""},{"id":43,"gu":"은평구","name":"구산주택","subway":"구산역","stage":"입주","total":238,"public":21,"private":217,"area":2177.6,"vacancy":0.018433,"special":1,"general":3,"moveIn":"2022-05-26","lastNotice":"2025-12-11","approval":"2019-12-24","construction":"2020-04-14","completion":"2022-05-18","operator":"주식회사 덕영","note":""},{"id":44,"gu":"마포구","name":"상수 크리원","subway":"상수역","stage":"입주","total":95,"public":27,"private":68,"area":642.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2021-05-15","lastNotice":"2021-02-08","approval":"2020-01-15","construction":"2020-03-09","completion":"2021-04-20","operator":"크리원","note":"최초"},{"id":45,"gu":"중랑구","name":"제이스타상봉","subway":"상봉역","stage":"입주","total":83,"public":6,"private":77,"area":907.0,"vacancy":0.051948,"special":0,"general":4,"moveIn":"2021-06-18","lastNotice":"2025-10-30","approval":"2019-12-31","construction":"2020-04-13","completion":"2021-06-07","operator":"(주)대원교역상사","note":""},{"id":46,"gu":"강서구","name":"포르투나블루","subway":"화곡역","stage":"입주","total":82,"public":15,"private":67,"area":707.9,"vacancy":0.134328,"special":3,"general":6,"moveIn":"2022-02-15","lastNotice":"2026-01-22","approval":"2020-06-18","construction":"2020-08-06","completion":"2022-01-27","operator":"권기범 외 3명","note":""},{"id":47,"gu":"관악구","name":"메트로움 지밸리퍼스트","subway":"구로디지털단지역","stage":"준공","total":240,"public":70,"private":170,"area":1499.8,"vacancy":0.0,"special":0,"general":0,"moveIn":None,"lastNotice":None,"approval":"2020-05-27","construction":"2020-08-11","completion":"2025-11-03","operator":"","note":""},{"id":49,"gu":"영등포구","name":"비스타동원","subway":"신풍역","stage":"입주","total":576,"public":70,"private":506,"area":7197.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2024-09-23","lastNotice":"2025-12-18","approval":"2020-04-09","construction":"2021-09-01","completion":"2024-10-08","operator":"㈜랜드코퍼레이션","note":"예비"},{"id":50,"gu":"강남구","name":"더원역삼","subway":"역삼역","stage":"입주","total":78,"public":19,"private":59,"area":640.4,"vacancy":0.016949,"special":0,"general":1,"moveIn":"2023-05-12","lastNotice":"2026-01-08","approval":"2020-09-10","construction":"2021-01-14","completion":"2023-05-12","operator":"형윤준","note":""},{"id":51,"gu":"종로구","name":"청계로벤하임","subway":"동묘앞역","stage":"입주","total":139,"public":16,"private":123,"area":979.5,"vacancy":0.032520,"special":1,"general":3,"moveIn":"2023-09-18","lastNotice":"2025-12-24","approval":"2020-11-10","construction":"2021-03-16","completion":"2023-09-18","operator":"이승은 외 3인","note":""},{"id":52,"gu":"은평구","name":"연신내역 루체스테이션","subway":"연신내역","stage":"입주","total":264,"public":74,"private":190,"area":1287.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2024-01-20","lastNotice":"2026-01-08","approval":"2020-07-02","construction":"2021-02-18","completion":"2024-01-24","operator":"주식회사 위드웰에셋","note":"예비"},{"id":53,"gu":"은평구","name":"THE STUDIO 163 (더스튜디오 163)","subway":"연신내역","stage":"입주","total":163,"public":16,"private":147,"area":656.2,"vacancy":0.0,"special":0,"general":0,"moveIn":"2024-06-01","lastNotice":"2025-10-16","approval":"2021-06-04","construction":"2022-04-29","completion":"2024-05-08","operator":"유한회사 자산하우징","note":"예비"},{"id":54,"gu":"중구","name":"166타워","subway":"동대문역사문화공원역","stage":"입주","total":105,"public":21,"private":84,"area":510.7,"vacancy":0.047619,"special":1,"general":3,"moveIn":"2023-10-11","lastNotice":"2025-11-06","approval":"2021-01-07","construction":"2021-09-28","completion":"2023-10-11","operator":"태성청년주택","note":""},{"id":55,"gu":"영등포구","name":"준타워","subway":"신길역","stage":"입주","total":162,"public":34,"private":128,"area":1185.0,"vacancy":0.046875,"special":0,"general":6,"moveIn":"2023-08-07","lastNotice":"2025-07-09","approval":"2020-09-10","construction":"2021-02-17","completion":"2023-07-14","operator":"주식회사 제이케이스타 대표이사 이준훈","note":""},{"id":56,"gu":"강북구","name":"에드가 수유","subway":"화계역","stage":"준공","total":426,"public":117,"private":309,"area":1895.0,"vacancy":0.0,"special":0,"general":0,"moveIn":None,"lastNotice":None,"approval":"2020-11-12","construction":"2022-09-30","completion":"2025-10-02","operator":"","note":""},{"id":57,"gu":"구로구","name":"에드가 개봉","subway":"개봉역","stage":"준공","total":268,"public":50,"private":218,"area":1938.0,"vacancy":0.0,"special":0,"general":0,"moveIn":None,"lastNotice":None,"approval":"2020-11-05","construction":"2022-07-22","completion":"2025-04-24","operator":"","note":""},{"id":58,"gu":"성북구","name":"성북 펠릭스","subway":"숭곡초교역","stage":"입주","total":299,"public":59,"private":240,"area":1171.0,"vacancy":0.004167,"special":0,"general":1,"moveIn":"2025-03-05","lastNotice":"2025-11-20","approval":"2020-12-03","construction":"2021-03-31","completion":"2025-01-31","operator":"꿈꾸는이상㈜","note":""},{"id":60,"gu":"송파구","name":"문정역 마에스트로","subway":"문정역","stage":"입주","total":438,"public":153,"private":285,"area":1955.8,"vacancy":0.129825,"special":8,"general":29,"moveIn":"2024-02-29","lastNotice":"2026-01-22","approval":"2020-12-10","construction":"2021-05-10","completion":"2024-01-19","operator":"","note":""},{"id":61,"gu":"관악구","name":"센터스퀘어 서울대","subway":"서울대벤처타운역","stage":"입주","total":418,"public":94,"private":324,"area":4472.7,"vacancy":0.074074,"special":2,"general":22,"moveIn":"2024-10-05","lastNotice":"2025-04-24","approval":"2020-12-17","construction":"2021-10-06","completion":"2024-08-14","operator":"캡스톤서림역청년주택일반사모부동산투자 유한회사","note":""},{"id":62,"gu":"동대문구","name":"에드가 휘경","subway":"회기역","stage":"준공","total":349,"public":36,"private":313,"area":2278.8,"vacancy":0.0,"special":0,"general":0,"moveIn":None,"lastNotice":None,"approval":"2020-12-31","construction":"2022-07-20","completion":"2025-04-21","operator":"","note":""},{"id":63,"gu":"은평구","name":"루미노 816","subway":"연신내역","stage":"입주","total":299,"public":119,"private":180,"area":2059.0,"vacancy":0.027778,"special":2,"general":3,"moveIn":"2024-12-02","lastNotice":"2025-10-02","approval":"2020-12-31","construction":"2021-11-22","completion":"2024-11-05","operator":"(주)에이치엔비개발","note":""},{"id":64,"gu":"노원구","name":"에드가 상계","subway":"수락산역","stage":"준공","total":443,"public":105,"private":338,"area":2379.0,"vacancy":0.0,"special":0,"general":0,"moveIn":None,"lastNotice":None,"approval":"2021-01-21","construction":"2022-08-25","completion":"2025-05-15","operator":"","note":""},{"id":68,"gu":"강동구","name":"길동생활A","subway":"길동역","stage":"입주","total":297,"public":110,"private":187,"area":1541.5,"vacancy":0.048128,"special":3,"general":6,"moveIn":"2025-02-17","lastNotice":"2026-01-29","approval":"2021-02-04","construction":"2022-07-08","completion":"2024-12-04","operator":"(주)대한제37호위탁관리부동산투자회사","note":""},{"id":69,"gu":"강동구","name":"길동생활B","subway":"길동역","stage":"입주","total":270,"public":71,"private":199,"area":1333.8,"vacancy":0.040201,"special":0,"general":8,"moveIn":"2025-02-17","lastNotice":"2026-01-29","approval":"2021-02-04","construction":"2022-06-29","completion":"2024-12-04","operator":"(주)대한제37호위탁관리부동산투자회사","note":""},{"id":70,"gu":"동대문구","name":"장안동 하트리움","subway":"장한평역","stage":"입주","total":284,"public":139,"private":145,"area":1175.0,"vacancy":0.006897,"special":1,"general":0,"moveIn":"2025-03-01","lastNotice":"2025-12-31","approval":"2021-04-01","construction":"2022-04-29","completion":"2025-03-18","operator":"주식회사 씨드원","note":""},{"id":71,"gu":"중랑구","name":"상봉 동양엔파트","subway":"상봉역","stage":"입주","total":299,"public":102,"private":197,"area":1440.6,"vacancy":0.015228,"special":0,"general":3,"moveIn":"2024-07-01","lastNotice":"2026-02-05","approval":"2021-04-01","construction":"2021-12-20","completion":"2024-06-17","operator":"김대용","note":""},{"id":72,"gu":"구로구","name":"세이지움 개봉","subway":"개봉역","stage":"입주","total":605,"public":273,"private":332,"area":4519.8,"vacancy":0.021084,"special":3,"general":4,"moveIn":"2025-04-28","lastNotice":"2026-01-08","approval":"2021-04-15","construction":"2021-10-18","completion":"2025-03-31","operator":"개봉아이알디피에프브이㈜","note":""},{"id":73,"gu":"동작구","name":"사당역 코브(COVE)","subway":"사당역","stage":"입주","total":152,"public":24,"private":128,"area":703.7,"vacancy":0.0,"special":0,"general":0,"moveIn":"2024-08-30","lastNotice":"2024-07-23","approval":"2021-07-19","construction":"2021-10-01","completion":"2024-02-07","operator":"이상현 외 1인","note":"최초"},{"id":75,"gu":"노원구","name":"광운대역 현대프라힐스","subway":"광운대역","stage":"입주","total":275,"public":95,"private":180,"area":2132.0,"vacancy":1.0,"special":38,"general":142,"moveIn":"2026-03-04","lastNotice":"2026-01-27","approval":"2021-06-10","construction":"2022-04-29","completion":"2025-05-21","operator":"현대아산㈜","note":"최초"},{"id":77,"gu":"동작구","name":"골든노블레스","subway":"신대방삼거리역","stage":"입주","total":110,"public":40,"private":70,"area":815.8,"vacancy":0.014286,"special":0,"general":1,"moveIn":"2024-01-24","lastNotice":"2025-11-13","approval":"2021-11-15","construction":"2022-03-17","completion":"2023-11-24","operator":"이영희","note":""},{"id":78,"gu":"중랑구","name":"세이지움 상봉","subway":"상봉역","stage":"입주","total":782,"public":382,"private":400,"area":4069.0,"vacancy":0.3625,"special":0,"general":145,"moveIn":"2025-12-08","lastNotice":"2026-01-29","approval":"2021-07-01","construction":"2021-09-29","completion":"2025-07-01","operator":"상봉아이알디피에프브이㈜","note":""},{"id":80,"gu":"노원구","name":"해링턴플레이스 노원 센트럴","subway":"노원역","stage":"입주","total":299,"public":88,"private":150,"area":2892.3,"vacancy":1.0,"special":31,"general":119,"moveIn":"2026-01-26","lastNotice":"2025-12-23","approval":"2021-07-22","construction":"2022-11-11","completion":"2025-10-01","operator":"주식회사 엘앤피개발","note":""},{"id":84,"gu":"용산구","name":"어반허브 서울스테이션","subway":"서울역","stage":"입주","total":265,"public":113,"private":152,"area":2581.4,"vacancy":0.006579,"special":0,"general":1,"moveIn":"2025-06-05","lastNotice":"2026-01-08","approval":"2021-08-12","construction":"2022-08-01","completion":"2025-03-31","operator":"(주)에버그린플라자","note":""},{"id":85,"gu":"성동구","name":"라봄성동","subway":"왕십리역","stage":"입주","total":346,"public":114,"private":232,"area":3051.0,"vacancy":0.275862,"special":2,"general":62,"moveIn":"2025-06-12","lastNotice":"2025-12-24","approval":"2021-08-19","construction":"2022-12-16","completion":"2025-05-30","operator":"인트러스제1호전문투자형사모부동산투자(유)","note":""},{"id":86,"gu":"동대문구","name":"리스트 안암","subway":"고려대역","stage":"입주","total":299,"public":129,"private":170,"area":2989.3,"vacancy":0.052941,"special":0,"general":9,"moveIn":"2024-11-04","lastNotice":"2026-02-05","approval":"2021-09-02","construction":"2022-05-24","completion":"2024-08-19","operator":"주식회사 브이인마크청년주택위탁관리부동산투자회사","note":""},{"id":87,"gu":"성북구","name":"라온프라이빗 종암","subway":"종암경찰서역","stage":"입주","total":290,"public":117,"private":173,"area":3013.0,"vacancy":0.248555,"special":7,"general":36,"moveIn":"2025-06-16","lastNotice":"2025-10-30","approval":"2021-09-16","construction":"2022-04-10","completion":"2025-06-02","operator":"주식회사 종암피에프브이","note":""},{"id":91,"gu":"광진구","name":"백악관타워","subway":"아차산역","stage":"입주","total":261,"public":101,"private":160,"area":2331.0,"vacancy":0.39375,"special":3,"general":60,"moveIn":"2025-12-08","lastNotice":"2025-12-24","approval":"2021-10-14","construction":"2022-07-28","completion":"2025-07-08","operator":"(주)더블유앤홀딩스","note":""},{"id":95,"gu":"동작구","name":"골드타워","subway":"신대방삼거리역","stage":"입주","total":330,"public":164,"private":166,"area":1426.0,"vacancy":0.006024,"special":0,"general":1,"moveIn":"2025-03-04","lastNotice":"2025-11-06","approval":"2021-10-21","construction":"2022-06-28","completion":"2025-02-10","operator":"금성종합건설 주식회사","note":""},{"id":96,"gu":"광진구","name":"리마크빌 구의","subway":"구의역","stage":"입주","total":439,"public":85,"private":354,"area":2031.9,"vacancy":1.0,"special":73,"general":281,"moveIn":"2026-03-23","lastNotice":"2026-01-27","approval":"2021-11-05","construction":"2022-07-22","completion":"2025-12-18","operator":"㈜마스턴제124호위탁관리부동산투자회사","note":""},{"id":98,"gu":"동대문구","name":"UNIT125(유니트125)","subway":"장한평역","stage":"착공신고","total":125,"public":14,"private":111,"area":923.9,"vacancy":1.0,"special":23,"general":88,"moveIn":None,"lastNotice":"2025-12-23","approval":"2022-10-20","construction":"2023-06-15","completion":None,"operator":"동서빌딩","note":""},{"id":100,"gu":"광진구","name":"더포디엄 830","subway":"건대입구역","stage":"입주","total":480,"public":167,"private":313,"area":2236.9,"vacancy":0.025559,"special":8,"general":0,"moveIn":"2025-02-28","lastNotice":"2026-01-15","approval":"2021-11-25","construction":"2022-07-15","completion":"2025-02-06","operator":"㈜엘앤케이이스테이트","note":""},{"id":101,"gu":"강서구","name":"센터스퀘어 발산","subway":"발산역","stage":"입주","total":716,"public":258,"private":458,"area":5366.9,"vacancy":0.117904,"special":21,"general":33,"moveIn":"2025-06-10","lastNotice":"2025-07-23","approval":"2021-12-16","construction":"2022-05-16","completion":"2025-03-27","operator":"캡스톤발산역청년주택일반사모부동산투자유한회사","note":""},{"id":103,"gu":"용산구","name":"남영역 롯데캐슬 헤리티지","subway":"남영역","stage":"입주","total":269,"public":52,"private":217,"area":1905.4,"vacancy":0.0,"special":0,"general":0,"moveIn":"2025-06-01","lastNotice":"2025-04-09","approval":"2021-12-23","construction":"2022-05-24","completion":"2025-05-28","operator":"롯데건설㈜","note":"최초"},{"id":104,"gu":"강남구","name":"도곡 더써밋타워","subway":"양재역","stage":"입주","total":209,"public":77,"private":132,"area":1010.9,"vacancy":0.053030,"special":0,"general":7,"moveIn":"2025-06-05","lastNotice":"2025-11-27","approval":"2021-12-30","construction":"2022-10-06","completion":"2025-04-11","operator":"코레이트도곡동청년주택전문투자형사모부동산투자 유한회사","note":""},{"id":106,"gu":"성동구","name":"한영스테이","subway":"마장역","stage":"입주","total":130,"public":50,"private":80,"area":1047.3,"vacancy":0.325,"special":0,"general":26,"moveIn":"2025-05-19","lastNotice":"2025-07-02","approval":"2022-02-24","construction":"2023-04-24","completion":"2025-04-10","operator":"한상(한석일 외 3명)","note":""},{"id":107,"gu":"노원구","name":"이니티움","subway":"태릉입구역","stage":"입주","total":100,"public":49,"private":51,"area":1032.0,"vacancy":0.019608,"special":0,"general":1,"moveIn":"2024-10-17","lastNotice":"2025-12-04","approval":"2022-03-03","construction":"2023-02-01","completion":"2024-10-15","operator":"유한책임회사 문하","note":""},{"id":108,"gu":"중랑구","name":"와이 센트럴시티 상봉","subway":"상봉역","stage":"입주","total":351,"public":175,"private":176,"area":1594.0,"vacancy":0.346591,"special":9,"general":52,"moveIn":"2025-11-10","lastNotice":"2026-01-08","approval":"2022-03-31","construction":"2022-11-14","completion":"2025-07-25","operator":"상봉동케이원청년주택피에프브이㈜","note":""},{"id":114,"gu":"강서구","name":"아르체움 등촌","subway":"등촌역","stage":"입주","total":156,"public":52,"private":104,"area":1319.0,"vacancy":0.0,"special":0,"general":0,"moveIn":"2025-05-30","lastNotice":"2025-03-07","approval":"2022-06-30","construction":"2023-05-18","completion":"2025-04-21","operator":"윤호표 외 8인 (대현빌딩)","note":"최초"}]

# ── Geocoding ──────────────────────────────────────────────────────
GU_CENTERS = {
    "강남구":(37.5172,127.0473),"강동구":(37.5301,127.1238),"강북구":(37.6396,127.0253),
    "강서구":(37.5509,126.8495),"관악구":(37.4784,126.9516),"광진구":(37.5384,127.0826),
    "구로구":(37.4954,126.8874),"금천구":(37.4570,126.8954),"노원구":(37.6542,127.0568),
    "도봉구":(37.6688,127.0471),"동대문구":(37.5744,127.0395),"동작구":(37.5124,126.9393),
    "마포구":(37.5663,126.9014),"서대문구":(37.5791,126.9368),"서초구":(37.4837,127.0324),
    "성동구":(37.5634,127.0369),"성북구":(37.5894,127.0167),"송파구":(37.5145,127.1059),
    "양천구":(37.5170,126.8666),"영등포구":(37.5264,126.8962),"용산구":(37.5323,126.9906),
    "은평구":(37.6026,126.9292),"종로구":(37.5735,126.9790),"중구":(37.5640,126.9975),
    "중랑구":(37.6063,127.0926),
}
_GEO_CACHE: dict = {}

def geocode(address: str, gu: str, station: str | None = None) -> tuple:
    key = address or ''
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]
    if key:
        try:
            time.sleep(1.1)
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": key + " 서울", "format": "json", "limit": 1},
                headers={"User-Agent": "SeoulHousingDashboard/1.0"},
                timeout=10,
            )
            data = resp.json()
            if data:
                r = (float(data[0]["lat"]), float(data[0]["lon"]))
                _GEO_CACHE[key] = r
                return r
        except Exception:
            pass
    # 역 좌표 fallback
    if station:
        stn = re.sub(r'역$', '', station)
        stn_clean = re.sub(r'\(.*?\)', '', stn).strip()
        for s in (stn, stn_clean):
            if s in STATION_COORDS:
                return STATION_COORDS[s]
    return GU_CENTERS.get(gu, (37.5665, 126.9780))

# ── API 수집 ──────────────────────────────────────────────────────
def fetch_all_notices():
    notices, page = [], 1
    while True:
        payload = f"bbsId=BMSR00015&pageIndex={page}&searchAdresGu=&searchCondition=&searchKeyword=&optn2=&optn5="
        try:
            resp = requests.post(API_URL, data=payload, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[WARN] page {page} 실패: {e}")
            break
        items = data.get("resultList", [])
        if not items:
            break
        for item in items:
            d = (item.get("optn1","") or "").replace("/","-")[:10]
            if d and d > CUTOFF_DATE:
                continue
            notices.append(item)
        paging   = data.get("pagingInfo", {})
        tot_page = int(paging.get("totPage", paging.get("lastPage", 1)))
        print(f"[INFO] page {page}/{tot_page} ({len(items)}건)")
        if page >= tot_page:
            break
        page += 1
        time.sleep(0.3)
    return notices

def fetch_notice_detail(ntt_id: str) -> dict:
    if not ntt_id:
        return {}
    url = f"{DETAIL_BASE}?nttId={ntt_id}&bbsId=BMSR00015"
    try:
        time.sleep(0.5)
        resp = requests.get(url, headers={**HEADERS,"Content-Type":"text/html"}, timeout=15)
        resp.encoding = "utf-8"
        text = resp.text
        result = {"detailUrl": url}
        cp = re.search(
            r'(?:시공사|건설사|시공업체|시공자)[^\w가-힣]*[:：]?\s*([가-힣a-zA-Z0-9(주)㈜\s]+?)(?:<|[\r\n]|,|　)',
            text)
        if cp: result["contractor"] = cp.group(1).strip()
        ap = re.search(
            r'href=["\']([^"\']*(?:apply|youth|soco|seoul)[^"\']*)["\'][^>]*>\s*(?:청약|신청|입주신청)',
            text, re.IGNORECASE)
        if ap:
            href = ap.group(1)
            result["applyUrl"] = href if href.startswith("http") else "https://soco.seoul.go.kr" + href
        return result
    except Exception as e:
        print(f"[WARN] 상세페이지 파싱 실패 nttId={ntt_id}: {e}")
        return {"detailUrl": url}

def match_complex(title: str, data_list: list):
    """공고 제목에서 단지 매칭 — 역명 가중치 포함 스코어링"""
    t = re.sub(r'[\[\]（）()]', '', title).lower()
    best, best_score = None, 0
    for d in data_list:
        score = 0
        n = d["name"].lower()
        subway = re.sub(r'역$', '', d.get("subway","")).lower()
        # 단지명 완전 포함 시 높은 점수
        if n in t or t in n:
            score = 100 + len(n)
        else:
            words = [w for w in re.split(r'[\s\-_]+', n) if len(w) >= 3]
            score = sum(10 for w in words if w in t)
        # 역명 포함 시 보너스 (이름이 겹치는 단지 구분 핵심)
        if subway and subway in t:
            score += 50
        if score > best_score:
            best_score = score
            best = d
    return best if best_score > 0 else None

def map_type(v): return {"1":"최초","2":"추가"}.get(str(v), str(v) if v else "")
def map_house(v): return {"1":"공공","2":"민간"}.get(str(v), str(v) if v else "")

# ── 메인 ──────────────────────────────────────────────────────────
def main():
    print(f"[INFO] 기준일: {CUTOFF_DATE} 23:59:59 KST")

    # ── 기존 좌표 캐시 로드 ───────────────────────────────────────
    existing_coords: dict = {}
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, 'r', encoding='utf-8') as f:
                old = json.load(f)
            for c in old.get('complexes', []):
                key = f"{c.get('gu','')}|{c.get('subway','')}|{c.get('private',0)}"
                if c.get('lat') and c.get('lng'):
                    existing_coords[key] = (c['lat'], c['lng'])
            print(f"[INFO] 기존 좌표 {len(existing_coords)}개 캐시 로드")
        except Exception:
            pass

    # ── PDF 파싱 ─────────────────────────────────────────────────
    pdf_rows: list = []
    if os.path.exists(PDF_PATH):
        pdf_rows = parse_pdf_complexes(PDF_PATH)
        if len(pdf_rows) < 80:
            print(f"[WARN] PDF 파싱 결과 부족 ({len(pdf_rows)}개). BASE_DATA만 사용.")
            pdf_rows = []
    else:
        print(f"[WARN] PDF 없음: {PDF_PATH}. BASE_DATA만 사용.")

    # ── 단지 목록 구성 ───────────────────────────────────────────
    all_complexes: list = []
    matched_base_ids: set = set()

    if pdf_rows:
        for pdf_row in pdf_rows:
            base = find_base_match(pdf_row, BASE_DATA, matched_base_ids) if pdf_row['subway'] else None
            if base:
                c = dict(base)
                c['address']      = pdf_row['address']   # geocoding용 주소
                c['tableVisible'] = True
                matched_base_ids.add(base['id'])
            else:
                # 지도 전용 단지
                station = pdf_row['subway'] or ''
                c = {
                    'id':           f"pdf_{pdf_row['pdfId'] or len(all_complexes)}",
                    'gu':           pdf_row['gu'],
                    'name':         pdf_row['address'],   # 단지명 없으므로 주소 사용
                    'subway':       station,
                    'subwayFormatted': format_station(station) if station else '',
                    'stage':        pdf_row['stage'],
                    'total':        pdf_row['total'],
                    'public':       pdf_row['public'],
                    'private':      pdf_row['private'],
                    'address':      pdf_row['address'],
                    'approval':     pdf_row['approval'],
                    'construction': pdf_row['construction'],
                    'completion':   pdf_row['completion'],
                    'moveIn':       pdf_row['moveIn'],
                    'vacancy':      None,
                    'lastNotice':   None,
                    'notices':      [],
                    'tableVisible': False,
                }
            all_complexes.append(c)

        # BASE_DATA에서 PDF 매칭 안 된 항목 추가 (예외 상황)
        for b in BASE_DATA:
            if b['id'] not in matched_base_ids:
                c = dict(b)
                c['tableVisible'] = True
                all_complexes.append(c)
                print(f"[WARN] PDF 미매칭 BASE_DATA: id={b['id']} {b['name']}")
    else:
        # PDF 없을 때 BASE_DATA만
        for b in BASE_DATA:
            c = dict(b)
            c['tableVisible'] = True
            all_complexes.append(c)

    # ── 역명 포맷 보강 ───────────────────────────────────────────
    for c in all_complexes:
        if not c.get('subwayFormatted') and c.get('subway'):
            c['subwayFormatted'] = format_station(c['subway'])

    # ── API 공고 수집 및 매칭 ────────────────────────────────────
    table_complexes = [c for c in all_complexes if c.get('tableVisible')]
    notices_map = {str(c['id']): [] for c in table_complexes}

    print("[INFO] 서울시 API 수집 중...")
    try:
        notices = fetch_all_notices()
        print(f"[INFO] 총 {len(notices)}건 수집")
        for item in notices:
            title    = item.get("nttSj","")
            date_str = (item.get("optn1","") or "").replace("/","-")[:10]
            ntt_id   = item.get("nttId","")
            board_id = item.get("boardId","")
            ntype    = map_type(item.get("optn5",""))
            house    = map_house(item.get("optn2",""))
            apply_dt = item.get("optn4","")
            url = (f"{DETAIL_BASE}?nttId={ntt_id}&bbsId=BMSR00015" if ntt_id
                   else f"{DETAIL_BASE}?boardId={board_id}&bbsId=BMSR00015" if board_id else "")

            matched = match_complex(title, table_complexes)
            if matched:
                cid = str(matched['id'])
                if date_str and (not matched.get("lastNotice") or date_str > matched["lastNotice"]):
                    matched["lastNotice"] = date_str
                notices_map[cid].append({
                    "title": title, "type": ntype, "house": house,
                    "date": date_str, "applyDate": apply_dt, "url": url,
                })
                if ntt_id and (not matched.get("contractor") or not matched.get("applyUrl")):
                    detail = fetch_notice_detail(ntt_id)
                    if detail.get("contractor") and not matched.get("contractor"):
                        matched["contractor"] = detail["contractor"]
                    if detail.get("applyUrl") and not matched.get("applyUrl"):
                        matched["applyUrl"] = detail["applyUrl"]
    except Exception as e:
        print(f"[WARN] API 수집 실패: {e}")

    for c in table_complexes:
        c['notices'] = notices_map.get(str(c['id']), [])

    # ── Geocoding ────────────────────────────────────────────────
    print("[INFO] Geocoding 중...")
    for c in all_complexes:
        geo_key = f"{c.get('gu','')}|{c.get('subway','')}|{c.get('private',0)}"
        if geo_key in existing_coords:
            c['lat'], c['lng'] = existing_coords[geo_key]
            continue
        addr    = c.get('address') or c.get('name','')
        station = c.get('subway')
        lat, lng = geocode(addr, c['gu'], station)
        c['lat'] = lat
        c['lng'] = lng

    # ── KPI (테이블 단지 기준) ────────────────────────────────────
    total_complexes  = len(table_complexes)
    active_complexes = sum(1 for c in table_complexes if c.get('stage') == '입주')
    total_private    = sum(c.get('private',0) for c in table_complexes)
    vacancy_units    = sum(round(c.get('private',0)*(c.get('vacancy') or 0)) for c in table_complexes)
    avg_vr           = round(vacancy_units/total_private*100, 1) if total_private else 0.0

    output = {
        "updatedAt": NOW_KST.strftime("%Y-%m-%d %H:%M"),
        "kpi": {
            "totalComplexes":    total_complexes,
            "activeComplexes":   active_complexes,
            "totalPrivateUnits": total_private,
            "vacancyUnits":      vacancy_units,
            "avgVacancyRate":    avg_vr,
        },
        "complexes": all_complexes,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    total_map = len(all_complexes)
    print(f"[INFO] data.json 저장 완료 (테이블 {total_complexes}개 / 지도 {total_map}개)")

if __name__ == "__main__":
    main()
