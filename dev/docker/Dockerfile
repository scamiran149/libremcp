FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    imagemagick librsvg2-bin make rsync \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyyaml

# Work directory persists via volume
WORKDIR /work

ENTRYPOINT ["make", "-C", "/work"]
CMD ["build"]
