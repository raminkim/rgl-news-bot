import os
import asyncpg

SQL_UPDATE_NEWS_STATE = "UPDATE news_state SET last_processed_at = $1 WHERE game = $2"
SQL_SELECT_NEWS_STATE = "SELECT game, last_processed_at FROM news_state"
SQL_UPDATE_CHANNEL_STATE = "UPDATE news_channel SET lol = $1, valorant = $2, overwatch = $3 WHERE channel_id = $4"

SQL_INSERT_CHANNEL_STATE = "INSERT INTO news_channel (channel_id, lol, valorant, overwatch) VALUES ($1, $2, $3, $4)"
SQL_SELECT_CHANNEL_STATE = "SELECT lol, valorant, overwatch FROM news_channel WHERE channel_id = $1"
SQL_SELECT_ALL_CHANNEL_STATE = "SELECT channel_id, lol, valorant, overwatch FROM news_channel"
SQL_DELETE_CHANNEL_STATE = "DELETE FROM news_channel WHERE channel_id = $1"

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
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_SELECT_NEWS_STATE)
            return {row["game"]: row["last_processed_at"] for row in rows}
    except asyncpg.PostgresError as e:
        print(f"❌ load_state 오류: {e}")
        return {}

async def save_channel_state(channel_id: int, games: dict[str, bool]) -> bool:
    """
    데이터베이스 테이블에 해당 채널의 게임 뉴스 설정값을 저장한다.

    Args:
        channel_id (int): 채널 ID
        games (dict[str, bool]): 게임 뉴스 설정 (롤, 발로란트, 오버워치)

    Returns:
        bool: 성공 여부
    """
    try:
        async with pool.acquire() as conn:
            if await conn.fetch(SQL_SELECT_CHANNEL_STATE, channel_id):
                await conn.execute(SQL_UPDATE_CHANNEL_STATE, games["lol"], games["valorant"], games["overwatch"], channel_id)
            else:
                await conn.execute(SQL_INSERT_CHANNEL_STATE, channel_id, games["lol"], games["valorant"], games["overwatch"])

    except asyncpg.PostgresError as e:
        print(f"❌ save_channel_state 오류: {e}")
        return False

    return True

async def load_channel_state(channel_id: int) -> dict[str, bool]:
    """
    데이터베이스 테이블로부터 해당 채널의 게임 뉴스 설정값을 로드한다.

    Args:
        channel_id (int): 채널 ID

    Returns:
        dict: 해당 채널의 게임 뉴스 설정값 (롤, 발로란트, 오버워치)
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(SQL_SELECT_CHANNEL_STATE, channel_id)
            if not row:
                return {}

            return dict(row)
    except asyncpg.PostgresError as e:
        print(f"❌ load_channel_state 오류: {e}")
        return {}
    
async def load_all_channel_state() -> dict[int, dict[str, bool]]:
    """
    데이터베이스 테이블로부터 모든 채널의 게임 뉴스 설정값을 로드한다.
    """
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_SELECT_ALL_CHANNEL_STATE)
            return {row["channel_id"]: dict(row) for row in rows}
    except asyncpg.PostgresError as e:
        print(f"❌ load_all_channel_state 오류: {e}")
        return {}

async def delete_channel_state(channel_id: int):
    """
    데이터베이스 테이블에서 해당 채널의 게임 뉴스 설정값을 삭제한다.

    Args:
        channel_id (int): 채널 ID
    """
    try:
        async with pool.acquire() as conn:
            await conn.execute(SQL_DELETE_CHANNEL_STATE, channel_id)
    except asyncpg.PostgresError as e:
        print(f"❌ delete_channel_state 오류: {e}")