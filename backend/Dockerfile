ARG PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/backend

# System deps for Pillow / bcrypt wheels
# Use mirror + retries to avoid very slow/unstable apt downloads.
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' /etc/apt/sources.list.d/debian.sources; \
      sed -i 's|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list.d/debian.sources || true; \
    fi; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org/debian|https://mirrors.aliyun.com/debian|g' /etc/apt/sources.list || true; \
      sed -i 's|http://security.debian.org/debian-security|https://mirrors.aliyun.com/debian-security|g' /etc/apt/sources.list || true; \
    fi; \
    apt-get -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update; \
    apt-get install -y --no-install-recommends \
      build-essential \
      libjpeg62-turbo-dev \
      zlib1g-dev; \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_FALLBACK_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_PROGRESS_BAR=off
RUN set -eux; \
    installed=0; \
    for attempt in 1 2 3 4 5; do \
      if python -m pip install --no-cache-dir --retries 20 --default-timeout 300 --prefer-binary \
        -i "${PIP_INDEX_URL}" --extra-index-url "${PIP_FALLBACK_INDEX_URL}" \
        -r requirements.txt; then \
        installed=1; \
        break; \
      fi; \
      echo "pip install attempt ${attempt} failed, retrying..."; \
      sleep $((attempt * 10)); \
    done; \
    if [ "$installed" -eq 0 ]; then \
      echo "mirror install failed, falling back to official PyPI only..."; \
      python -m pip install --no-cache-dir --retries 20 --default-timeout 300 --prefer-binary \
        -i "https://pypi.org/simple" \
        -r requirements.txt; \
    fi

COPY backend /app/backend

EXPOSE 8000

RUN chmod +x /app/backend/entrypoint.sh

CMD ["/app/backend/entrypoint.sh"]
