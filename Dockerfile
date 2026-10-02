FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DOTII_RUNTIME_DIR=/data HOME=/data
ARG DEBIAN_MIRROR=deb.debian.org
RUN sed -i "s|http://deb.debian.org|https://${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources && apt-get -o Acquire::Retries=3 -o Acquire::https::Timeout=30 update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-noto-cjk ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-nas.txt ./
RUN pip install --no-cache-dir -r requirements-nas.txt && mkdir /data && chown 1000:1000 /data
COPY bridge/ ./bridge/
COPY docker/ ./docker/
RUN python docker/install_codex.py
ENV CODEX_HOME=/data/.codex DOTII_CODEX_QUOTA_ONLY=1 TZ=Asia/Shanghai
USER 1000:1000
EXPOSE 8787
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/health', timeout=3)" || exit 1
ENTRYPOINT ["python", "docker/start.py"]
