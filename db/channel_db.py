import asyncpg
from .connection import ensure_pool, get_pool

SQL_UPDATE_CHANNEL_STATE = "UPDATE news_channel SET lol = $1, valorant = $2, overwatch = $3 WHERE channel_id = $4"
SQL_INSERT_CHANNEL_STATE = "INSERT INTO news_channel (channel_id, lol, valorant, overwatch) VALUES ($1, $2, $3, $4)"
SQL_SELECT_CHANNEL_STATE = "SELECT lol, valorant, overwatch FROM news_channel WHERE channel_id = $1"
SQL_SELECT_ALL_CHANNEL_STATE = "SELECT channel_id, lol, valorant, overwatch FROM news_channel"
SQL_DELETE_CHANNEL_STATE = "DELETE FROM news_channel WHERE channel_id = $1"

async def save_channel_state(channel_id: int, games: dict[str, bool]) -> bool:
    """
    데이터베이스 테이블에 해당 채널의 게임 뉴스 설정값을 저장한다.

    Args:
        channel_id (int): 채널 ID
        games (dict[str, bool]): 게임 뉴스 설정 (롤, 발로란트, 오버워치)

    Returns:
        bool: 성공 여부
    """
    await ensure_pool()
    try:
        pool = get_pool()
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
    await ensure_pool()
    try:
        pool = get_pool()
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
    await ensure_pool()
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(SQL_SELECT_ALL_CHANNEL_STATE)
            return {row["channel_id"]: dict(row) for row in rows}
    except asyncpg.PostgresError as e:
        print(f"❌ load_all_channel_state 오류: {e}")
        return {}

async def delete_channel_state(channel_id: int) -> bool:
    """
    데이터베이스 테이블에서 해당 채널의 게임 뉴스 설정값을 삭제한다.

    Args:
        channel_id (int): 채널 ID

    Returns:
        bool: 삭제 성공 여부 (True: 삭제됨, False: 삭제할 데이터 없음 또는 오류)
    """
    await ensure_pool()
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(SQL_DELETE_CHANNEL_STATE, channel_id)
            deleted_count = int(result.split()[1])

            return deleted_count > 0

    except asyncpg.PostgresError as e:
        print(f"❌ delete_channel_state 오류: {e}")
        return False 