import aiohttp
import asyncio
import heapq
import os
import asyncpg

from typing import List, Dict, Any
from datetime import date

SQL_UPDATE_STATE = "UPDATE news_state SET last_processed_at = $1 WHERE game = $2"
SQL_SELECT_STATE = "SELECT game, last_processed_at FROM news_state"

pool = None

async def connect_db():
    global pool
    try:
        pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            ssl="require",
            min_size=1,
            max_size=5,
        )
        print("✅ DB 풀 생성 완료")
    except Exception as e:
        print(f"❌ DB 풀 생성 실패: {e}")
        raise 

async def ensure_pool():
    """풀(pool)이 없으면 connect_db()를 호출해 초기화한다."""
    global pool
    if pool is None:
        await connect_db()


async def save_state(game: str, last_at: int) -> None:
    """
    데이터베이스 테이블에 game별 lastProcessedAt을 기록한다.

    Args:
        game (str): lastProcessedAt을 기록할 key 값. (롤/발로란트/오버워치)
        last_at (int): 알림으로 남긴 마지막 기사의 createdAt 값.
    """
    await ensure_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute(SQL_UPDATE_STATE, last_at, game)
    except asyncpg.PostgresError as e:
        print(f"❌ save_state 오류: {e}")

async def load_state() -> dict[str, int]:
    """
    데이터베이스 테이블에서 lastProcessedAt을 가져온다.

    Returns:
        dict: lastProcessedAt이 key 값으로 담긴 dict를 로드한 값.
    """
    await ensure_pool()
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_SELECT_STATE)
            return {row["game"]: row["last_processed_at"] for row in rows}
    except asyncpg.PostgresError as e:
        print(f"❌ load_state 오류: {e}")
        return {}          # 안전한 기본값


async def update_state(game: str, articles: List[Dict[str, Any]]) -> None:
    """
    데이터베이스 테이블에 game별 lastProcessedAt을 최신화한다.

    Args:
        game (str): lastProcessedAt을 기록할 key 값. (롤/발로란트/오버워치)
        articles (List[Dict]): 마지막 처리 시각 이후에 생성된 기사 목록
    """
    if not articles:
        return
    
    max_at = max([article.get('createdAt', 0) for article in articles])
    await save_state(game, max_at)


async def lol_news_articles(formatted_date: str) -> List[Dict[str, Any]]:
    """
    주어진 날짜의 네이버 e스포츠(롤) 뉴스 목록을 비동기로 가져옵니다.

    Args:
        formatted_date (str): 'YYYY-MM-DD' 형식의 날짜 문자열

    Returns:
        List[Dict]: 해당 날짜의 신규 뉴스 기사 목록 (lastProcessedAt 이후 기사만 반환)
    """
    url = f'https://esports-api.game.naver.com/service/v1/news/list?sort=latest&newsType=lol&day={formatted_date}&page=1&pageSize=20'

    params = {
        'access-control-allow-credentials': 'true',
        'access-control-allow-origin': 'https://game.naver.com'
    }

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.15 Safari/537.36'
    }
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url=url, params=params, headers=headers) as response:
                data = await response.json()
                content = data.get("content", [])

        # 이전에 가져왔던 롤 이스포츠 기사 중 마지막으로 처리한 기사의 시각을 불러옴.
        state = await load_state()
        lol_last_at = state.get("lol", 0)

        # createdAt이 lol의 lastProcessedAt보다 큰(신규) 기사만 반환
        lol_new_articles = sorted(
            (a for a in content if a.get('createdAt', 0) > lol_last_at),
            key=lambda x: x['createdAt']
        )

        # 신규 기사가 있을 때만 상태 갱신
        if lol_new_articles:
            await update_state("lol", lol_new_articles)
        
        return lol_new_articles

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 로그 출력하거나 빈 리스트 반환
        print(f"❌ 롤 뉴스 API 요청 실패: {e}")
        return []
    

async def valorant_news_articles(formatted_date: str) -> List[Dict[str, Any]]:
    """
    주어진 날짜의 네이버 e스포츠(발로란트) 뉴스 목록을 비동기로 가져옵니다.

    Args:
        formatted_date (str): 'YYYY-MM-DD' 형식의 날짜 문자열

    Returns:
        List[Dict]: 해당 날짜의 신규 뉴스 기사 목록 (lastProcessedAt 이후 기사만 반환)
    """
    url = f'https://esports-api.game.naver.com/service/v1/news/list?sort=latest&newsType=valorant&day={formatted_date}&page=1&pageSize=20'

    params = {
        'access-control-allow-credentials': 'true',
        'access-control-allow-origin': 'https://game.naver.com'
    }

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.15 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params, headers=headers) as response:
                data = await response.json()
                content = data.get("content", [])

        state = await load_state()
        valorant_last_at = state.get("valorant", 0)

        # lastProcessedAt 이후에 생성된 신규 기사만 정렬하여 반환
        valorant_new_articles = sorted(
            (a for a in content if a.get('createdAt', 0) > valorant_last_at),
            key=lambda x: x['createdAt']
        )

        # 신규 기사가 있을 때만 상태 DB 갱신
        if valorant_new_articles:
            await update_state("valorant", valorant_new_articles)

        return valorant_new_articles

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 요청 실패 시 로그 출력 및 빈 리스트 반환
        print(f"❌ 발로란트 뉴스 API 요청 실패: {e}")
        return []


async def overwatch_news_articles(formatted_date: str) -> List[Dict[str, Any]]:
    """
    주어진 날짜의 네이버 e스포츠(오버워치) 뉴스 목록을 비동기로 가져옵니다.

    Args:
        formatted_date (str): 'YYYY-MM-DD' 형식의 날짜 문자열

    Returns:
        List[Dict]: 해당 날짜의 뉴스 기사 목록 (API 응답의 "content" 리스트)
    """
    url = f'https://esports-api.game.naver.com/service/v1/news/list?sort=latest&newsType=overwatch&day={formatted_date}&page=1&pageSize=20'

    params = {
        'access-control-allow-credentials': 'true',
        'access-control-allow-origin': 'https://game.naver.com'
    }

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Whale/4.32.315.15 Safari/537.36'
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params, headers=headers) as response:
                data = await response.json()
                content = data.get("content", [])

        state = await load_state()
        overwatch_last_at = state.get("overwatch", 0)

        # lastProcessedAt 이후에 생성된 신규 기사만 정렬하여 반환
        overwatch_new_articles = sorted(
            (a for a in content if a.get('createdAt', 0) > overwatch_last_at),
            key=lambda x: x['createdAt']
        )

        # 신규 기사가 있을 때만 상태 DB 갱신
        if overwatch_new_articles:
            await update_state("overwatch", overwatch_new_articles)

        return overwatch_new_articles

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 요청 실패 시 로그 출력 및 빈 리스트 반환
        print(f"❌ 오버워치 뉴스 API 요청 실패: {e}")
        return []


async def fetch_news_articles() -> List[Dict[str, Any]]:
    """
    네이버 e스포츠 뉴스 사이트에서 최신 기사를 가져와,
    마지막 처리 시각(lastProcessedAt) 이후에 생성된 기사만 필터링하여 반환합니다.

    Returns:
        List[Dict]: 해당 날짜의 신규 뉴스 기사 목록 (lastProcessedAt 이후 기사만 반환)
    """

    formatted_date = date.today().strftime('%Y-%m-%d')
    
    # LOL e-sports 뉴스를 크롤링하는 함수로 분리
    lol_new_articles = await lol_news_articles(formatted_date)

    # Valorant e-sports 뉴스를 크롤링하는 함수로 분리
    valorant_new_articles = await valorant_news_articles(formatted_date)

    # Overwatch e-sports 뉴스를 크롤링하는 함수로 분리
    overwatch_new_articles = await overwatch_news_articles(formatted_date)

    # 세 게임의 신규 기사 리스트를 createdAt 기준으로 정렬하며, 하나로 결합
    all_new_articles = list(heapq.merge(
        lol_new_articles, valorant_new_articles, overwatch_new_articles,
        key=lambda x: x['createdAt']
    ))

    return all_new_articles