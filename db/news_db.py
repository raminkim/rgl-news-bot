import asyncpg
from .connection import ensure_pool, get_pool

SQL_UPDATE_NEWS_STATE = "UPDATE news_state SET last_processed_at = $1 WHERE game = $2"
SQL_SELECT_NEWS_STATE = "SELECT game, last_processed_at FROM news_state"

async def save_state(game: str, last_at: int) -> None:
    """
    데이터베이스 테이블에 game별 lastProcessedAt을 기록한다.

    Args:
        game (str): lastProcessedAt을 기록할 key 값. (롤/발로란트/오버워치)
        last_at (int): 알림으로 남긴 마지막 기사의 createdAt 값.
    """
    await ensure_pool()
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await conn.execute(SQL_UPDATE_NEWS_STATE, last_at, game)
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
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_SELECT_NEWS_STATE)
            return {row["game"]: row["last_processed_at"] for row in rows}
    except asyncpg.PostgresError as e:
        print(f"❌ load_state 오류: {e}")
        return {} 