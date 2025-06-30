# 1. 가벼운 베이스 이미지 사용
FROM python:3.11-slim

# 2. 비루트(non-root) 유저 생성
RUN useradd --create-home --shell /bin/bash botuser

# 3. 작업 디렉터리 설정
WORKDIR /bot

# 4. 시스템 패키지 (최소)
#    - libjpeg / zlib: Pillow(이미지 처리) 컴파일 런타임
#    - fonts-dejavu-core: DejaVu Sans Bold 포함
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libjpeg-dev \
        zlib1g-dev \
        fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*

# 5. requirements.txt 먼저 복사 (캐시 레이어 활용)
COPY requirements.txt .

# 6. Python 의존성 설치 (캐시 비움)
RUN pip install --no-cache-dir -r requirements.txt

# 7. 소스 코드 전체 복사
COPY . .

# 8. 비루트 유저로 권한 전환
USER botuser

# 9. 실시간 로그 플러시
ENV PYTHONUNBUFFERED=1

# 10. 엔트리포인트
CMD ["python", "bot.py"]
