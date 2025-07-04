import aiohttp
from datetime import datetime, timezone


_TEAM_NAME_KEYS = (
    "teamCode",
    "nameAcronym",
    "shortName",
    "nameEng",
    "name",
)

# 팀 로고용 이미지 URL 후보 키
_TEAM_IMG_KEYS = (
    "imageUrl",
    "colorImageUrl",
    "whiteImageUrl",
    "blackImageUrl",
)

async def fetch_lol_league_schedule_months(year_str: str, league_str: str):
    """네이버 e스포츠 API에서 *해당 연도의 월 목록*을 가져옵니다.

    `/v1/schedule/year/months` 엔드포인트를 호출해 특정 연도에
    스케줄이 존재하는 월 정보를 반환합니다. 성공하면 원본 JSON을 그대로
    돌려주며, 실패(HTTP 200이 아님) 시 `None` 을 반환합니다.

    매개변수
        year_str (str): 4자리 연도 문자열. 예) 2024.
        league_str (str): 리그 식별자(`topLeagueId`). 예) LCK.

    반환값
        dict | None: 응답 코드가 200이면 JSON 딕셔너리, 아니면 `None`.
    """
    url = 'https://esports-api.game.naver.com/service/v1/schedule/year/months'

    params = {
        'year': year_str,
        'topLeagueId': league_str,
        'relay': 'false'
    }

    headers = {
        'origin': 'https://game.naver.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.22 Safari/537.36'
    }


    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                print(f"❌ 롤 일정 크롤링 실패: {response.status}")
                print(f"응답 내용: {response_text}")
                return None
            
async def fetch_monthly_league_schedule(year_month_str: str, league_str: str):
    """네이버 e스포츠 API에서 *특정 월*의 경기 일정을 가져옵니다.

    `/v2/schedule/month` 엔드포인트를 호출해 주어진 월(YYYYMM)과
    리그에 해당하는 경기 정보를 받아옵니다. 이 함수는 네트워크 요청만
    수행하고, 파싱은 `parse_lol_month_days()` 에서 담당합니다.

    매개변수
        year_month_str (str): 연월 문자열 `YYYYMM`. 예) 202404.
        league_str (str): 리그 식별자(`topLeagueId`).

    반환값
        dict | None: 성공 시 JSON 딕셔너리, 실패 시 `None`.
    """
    url = 'https://esports-api.game.naver.com/service/v2/schedule/month'

    params = {
        'month': year_month_str,
        'topLeagueId': league_str,
        'relay': 'false'
    }

    headers = {
        'origin': 'https://game.naver.com',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.22 Safari/537.36'
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                response_text = await response.text()
                print(f"❌ 롤 일정 크롤링 실패: {response.status}")
                print(f"응답 내용: {response_text}")

def _find_team_name(team: dict | None) -> str | None:
    """팀 객체 딕셔너리에서 사용하기 좋은 이름을 찾아 반환합니다."""
    if not isinstance(team, dict):
        return None
    for key in _TEAM_NAME_KEYS:
        val = team.get(key)
        if val:
            return str(val)
    return None


def _normalize_start_date(value):
    """startDate 값이 epoch(ms) 이면 ISO 문자열로 변환하고, 이미 문자열이면 그대로 반환"""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()
    return str(value)

def _extract_match_basic(match_obj: dict) -> dict:
    """내부 match 객체에서 핵심 정보를 추려낸다.
    반환 필드
        matchId, startDate(ISO), status, leagueName, blockName, team1, team2
    일부 필드는 소스 JSON 버전에 따라 키가 다를 수 있어 최대한 유연하게 대응한다.
    """
    # 기본 키 매핑
    match_id = match_obj.get("matchId") or match_obj.get("id")
    start_date = _normalize_start_date(match_obj.get("startDate") or match_obj.get("startTime"))
    status = match_obj.get("status") or match_obj.get("matchStatus")
    league_name = match_obj.get("leagueName") or match_obj.get("league")
    block_name = match_obj.get("blockName") or match_obj.get("stageName")

    # 점수 추출 (진행 중/종료 경기)
    score1 = match_obj.get("homeScore") or match_obj.get("team1Score") or match_obj.get("score1")
    score2 = match_obj.get("awayScore") or match_obj.get("team2Score") or match_obj.get("score2")

    # 팀 추출
    team1 = team2 = None
    img1 = img2 = None
    if "teams" in match_obj and isinstance(match_obj["teams"], list):
        teams_data = match_obj["teams"]
        if len(teams_data) >= 1:
            team1 = _find_team_name(teams_data[0])
            img1 = _find_team_img(teams_data[0])
        if len(teams_data) >= 2:
            team2 = _find_team_name(teams_data[1])
            img2 = _find_team_img(teams_data[1])
    elif "homeTeam" in match_obj or "awayTeam" in match_obj:
        # v2/month 응답 구조 (homeTeam / awayTeam)
        home = match_obj.get("homeTeam")
        away = match_obj.get("awayTeam")
        team1 = _find_team_name(home)
        team2 = _find_team_name(away)
        img1 = _find_team_img(home)
        img2 = _find_team_img(away)
    else:
        # 평탄화된 키로 들어오는 경우 (team1Name / team2Name)
        team1 = match_obj.get("team1Name") or match_obj.get("homeTeamName")
        team2 = match_obj.get("team2Name") or match_obj.get("awayTeamName")

    return {
        "matchId": match_id,
        "startDate": start_date,
        "status": status,
        "leagueName": league_name,
        "blockName": block_name,
        "team1": team1,
        "team2": team2,
        "team1Img": img1,
        "team2Img": img2,
        "score1": score1,
        "score2": score2,
    }


def parse_lol_month_days(days_resp: dict) -> list[dict]:
    """schedule/month API 응답(JSON)을 받아 날짜 구분 없이 match 단위로 납작하게 반환.

    Args:
        days_resp (dict): fetch_lol_league_schedule_days() 로 받은 원본 JSON

    Returns:
        List[Dict]: 경기별 핵심 정보를 담은 리스트
    """
    if not days_resp or days_resp.get("code") != 200:
        return []

    matches: list[dict] = []

    content = days_resp.get("content")

    def _yield_match_objs(node):
        # content dict (v2) -> matches
        if isinstance(node, dict):
            if "matches" in node:
                for m in node["matches"]:
                    yield m
            elif "matchId" in node:
                yield node
            else:
                # date + matchList 구조
                ml = node.get("matchList") or node.get("matches")
                if ml:
                    for m in ml:
                        yield m
        elif isinstance(node, list):
            for item in node:
                yield from _yield_match_objs(item)

    for obj in _yield_match_objs(content):
        matches.append(_extract_match_basic(obj))

    return matches

def _find_team_img(team: dict | None) -> str | None:
    """팀 객체 딕셔너리에서 사용하기 좋은 로고 URL을 찾아 반환합니다."""
    if not isinstance(team, dict):
        return None
    for key in _TEAM_IMG_KEYS:
        url = team.get(key)
        if url:
            return str(url)
    return None