import aiohttp
import orjson
import asyncio
import heapq

from pathlib import Path
from typing import List, Dict
from datetime import date

STATE_FILE = Path("news_state.json")

def save_state(game: str, last_at: int):
    """
    'news_state.json'에 lastProcessedAt을 기록한다.

    Args:
        game (str): lastProcessedAt을 기록할 key 값. (롤/발로란트/오버워치)
        last_at (int): 알림으로 남긴 마지막 기사의 createdAt 값.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state = load_state()
    state[game] = {"lastProcessedAt": last_at } # 개임별로 마지막으로 처리한 시각
    STATE_FILE.write_bytes(orjson.dumps(state, option = orjson.OPT_INDENT_2))


def load_state() -> dict:
    """
    'news_state.json'에서 lastProcessedAt을 가져온다.

    Returns:
        dict: lastProcessedAt이 key 값으로 담긴 dict를 로드한 값.
    """
    if not STATE_FILE.exists():
        return {"lastProcessedAt": 0}
    return orjson.loads(STATE_FILE.read_bytes())


def update_state(game: str, articles: List[Dict]):
    """
    'news_state.json'에 lastProcessedAt을 최신화한다.

    Args:
        game (str): lastProcessedAt을 기록할 key 값. (롤/발로란트/오버워치)
        articles (List[Dict]): 마지막 처리 시각 이후에 생성된 기사 목록
    """
    max_at = max([article.get('createdAt', 0) for article in articles])
    save_state(game, max_at)


async def lol_news_articles(formatted_date: str) -> List[Dict]:
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
        async with aiohttp.ClientSession() as session:
            async with session.get(url=url, params=params, headers=headers) as response:
                data = await response.json()
                content = data.get("content", [])

        # 이전에 가져왔던 롤 이스포츠 기사 중 마지막으로 처리한 기사의 시각을 불러옴.
        lol_last_at = load_state().get("lol").get('lastProcessedAt', 0)

        # createdAt이 lol의 lastProcessedAt보다 큰(신규) 기사만 반환
        lol_new_articles = sorted(
            (a for a in content if a.get('createdAt', 0) > lol_last_at),
            key=lambda x: x['createdAt']
        )

        # 신규 기사가 있을 때만 상태 갱신
        if lol_new_articles:
            update_state("lol", lol_new_articles)
        
        return lol_new_articles

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 로그 출력하거나 빈 리스트 반환
        print(f"❌ 롤 뉴스 API 요청 실패: {e}")
        return []
    

async def valorant_news_articles(formatted_date) -> List[Dict]:
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

        # news_state.json에서 발로란트의 마지막 처리 시각을 불러옴
        valorant_last_at = load_state().get("valorant", {}).get('lastProcessedAt', 0)

        # lastProcessedAt 이후에 생성된 신규 기사만 정렬하여 반환
        valorant_new_articles = sorted(
            (a for a in content if a.get('createdAt', 0) > valorant_last_at),
            key=lambda x: x['createdAt']
        )

        # 신규 기사가 있을 때만 상태 파일 갱신
        if valorant_new_articles:
            update_state("valorant", valorant_new_articles)

        return valorant_new_articles

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 요청 실패 시 로그 출력 및 빈 리스트 반환
        print(f"❌ 발로란트 뉴스 API 요청 실패: {e}")
        return []


async def overwatch_news_articles(formatted_date) -> List[Dict]:
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

        # news_state.json에서 오버워치의 마지막 처리 시각을 불러옴
        overwatch_last_at = load_state().get("overwatch", {}).get('lastProcessedAt', 0)

        # lastProcessedAt 이후에 생성된 신규 기사만 정렬하여 반환
        overwatch_new_articles = sorted(
            (a for a in content if a.get('createdAt', 0) > overwatch_last_at),
            key=lambda x: x['createdAt']
        )

        # 신규 기사가 있을 때만 상태 파일 갱신
        if overwatch_new_articles:
            update_state("overwatch", overwatch_new_articles)

        return overwatch_new_articles

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 요청 실패 시 로그 출력 및 빈 리스트 반환
        print(f"❌ 오버워치 뉴스 API 요청 실패: {e}")
        return []


async def fetch_news_articles() -> List[Dict]:
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


if __name__ == '__main__':
    articles = asyncio.run(fetch_news_articles())
    print(f"신규 기사 {len(articles)}건:", articles)