import os
import asyncpg

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

def get_pool():
    """DB 풀을 반환한다."""
    return pool 