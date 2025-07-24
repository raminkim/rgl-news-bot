import aiohttp
import asyncio
import heapq

from typing import List, Dict, Any
from datetime import date


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
                lol_new_articles = data.get("content", [])
        
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
                valorant_new_articles = data.get("content", [])

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
                overwatch_new_articles = data.get("content", [])

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