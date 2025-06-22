# 1. 가벼운 베이스 이미지 사용
FROM python:3.11-slim

# 2. 비루트(non-root) 유저 생성
RUN useradd --create-home --shell /bin/bash botuser

# 3. 작업 디렉터리 설정
WORKDIR /bot

# 4. 의존성 설치 전 시스템 패키지 최소로 설치 (필요 시)
#    예) pip wheel 빌드에 필요한 gcc 등
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends gcc && \
#     rm -rf /var/lib/apt/lists/*

# 5. 캐시 활용을 위해 requirements.txt 먼저 복사
COPY requirements.txt .

# 6. pip 설치 시 캐시 제거로 이미지 크기 최적화
RUN pip install --no-cache-dir -r requirements.txt

# 7. 소스 코드 전체 복사
COPY . .

# 8. 비루트 유저로 권한 전환
USER botuser

# 9. 로그가 실시간 플러시되도록 설정
ENV PYTHONUNBUFFERED=1

# 10. 엔트리포인트
CMD ["python", "bot.py"]