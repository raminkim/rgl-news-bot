import os
import asyncpg

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