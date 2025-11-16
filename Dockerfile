FROM python:3.13 as builder
ARG BUILDX_QEMU_ENV
WORKDIR /usr/src/app
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
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip
RUN if [ "${BUILDX_QEMU_ENV}" = "true" ] && [ "$(getconf LONG_BIT)" = "32" ]; then \
        pip install -U cryptography==3.3.2; \
     fi
RUN pip install -r requirements.txt
FROM python:3.13-slim
LABEL description="Docker image for Twitch Channel Points Miner v2"
WORKDIR /usr/src/app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    libgomp1 \
    libgfortran5 \
    libblas3 \
    liblapack3 && \
    rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY ./TwitchChannelPointsMiner ./TwitchChannelPointsMiner
RUN groupadd -r miner && \
    useradd -r -g miner miner && \
    mkdir -p /usr/src/app/analytics /usr/src/app/cookies /usr/src/app/logs && \
    chown -R miner:miner /usr/src/app
USER miner
ENTRYPOINT [ "python", "run.py" ]
