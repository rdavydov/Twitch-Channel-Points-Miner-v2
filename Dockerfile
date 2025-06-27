FROM python:3.13 as builder
ARG BUILDX_QEMU_ENV
WORKDIR /app
COPY requirements.txt ./
ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -qq -y --no-install-recommends \
        gcc \
        libffi-dev \
        rustc \
        zlib1g-dev \
        libjpeg-dev \
        libssl-dev \
        libblas-dev \
        liblapack-dev \
        make \
        cmake \
        automake \
        ninja-build \
        g++ \
        subversion \
        python3-dev \
        build-essential \
    && pip install --upgrade pip setuptools wheel \
    && if [ "${BUILDX_QEMU_ENV}" = "true" ] && [ "$(getconf LONG_BIT)" = "32" ]; then \
           pip install -U cryptography==44.0.2; \
       fi \
    && pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim
LABEL description="Docker image for Twitch Channel Points Miner v2"
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY ./TwitchChannelPointsMiner ./TwitchChannelPointsMiner
RUN groupadd -r miner && useradd -r -g miner miner
RUN chown -R miner:miner /app
USER miner
ENTRYPOINT [ "python", "run.py" ]
