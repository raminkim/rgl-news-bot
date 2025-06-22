import aiohttp
import orjson
import asyncio

from pathlib import Path
from typing import List, Dict

STATE_FILE = Path("news_state.json")

def save_state(last_at: int):
    """
    'news_state.json'에 lastProcessedAt을 기록한다.

    Args:
        last_at (int): 알림으로 남긴 마지막 기사의 createdAt 값.
    """
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_bytes(orjson.dumps({
        "lastProcessedAt": last_at # 마지막으로 처리한 시각
    }, option = orjson.OPT_INDENT_2))


def load_state() -> dict:
    """
    'news_state.json'에서 lastProcessedAt을 가져온다.

    Returns:
        dict: lastProcessedAt이 key 값으로 담긴 dict를 로드한 값.
    """
    if not STATE_FILE.exists():
        return {"lastProcessedAt": 0}
    return orjson.loads(STATE_FILE.read_bytes())


def update_state(articles: List[Dict]):
    """
    'news_state.json'에 lastProcessedAt을 최신화한다.

    Args:
        articles (List[Dict]): 마지막 처리 시각 이후에 생성된 기사 목록
    """
    max_at = max([article.get('createdAt', 0) for article in articles])
    save_state(max_at)


async def fetch_news_articles() -> List[Dict]:
    """
    네이버 e스포츠 뉴스 사이트에서 최신 기사를 가져와,
    마지막 처리 시각(lastProcessedAt) 이후에 생성된 기사만 필터링하여 반환합니다.

    Returns:
        articles (List[Dict]): 마지막 처리 시각 이후에 생성된 기사 목록
    """
    url = 'https://esports-api.game.naver.com/service/v1/news/list?sort=latest&newsType=lol&day=2025-06-22&page=1&pageSize=20'

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

    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        # 로그 출력하거나 빈 리스트 반환
        print(f"❌ 뉴스 API 요청 실패: {e}")
        return []

    last_at = load_state().get('lastProcessedAt', 0)
        
    # createdAt이 lastProcessedAt보다 큰(신규) 기사만 반환    
    new_articles = sorted(
        (a for a in content if a.get('createdAt', 0) > last_at),
        key=lambda x: x['createdAt']
    )
    return new_articles


if __name__ == '__main__':
    articles = asyncio.run(fetch_news_articles())
    print(f"신규 기사 {len(articles)}건:", articles)