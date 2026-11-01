FROM node:24-bookworm-slim AS dashboard-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.10-bookworm

ARG BUILDX_QEMU_ENV

WORKDIR /usr/src/app

COPY requirements.txt pyproject.toml setup.py README.md LICENSE ./
COPY TwitchChannelPointsMiner ./TwitchChannelPointsMiner

ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

RUN pip install --upgrade pip

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -qq -y --no-install-recommends \
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
  && if [ "${BUILDX_QEMU_ENV}" = "true" ] && [ "$(getconf LONG_BIT)" = "32" ]; then \
        pip install -U cryptography==3.3.2; \
     fi \
  && pip install -r requirements.txt \
  && pip cache purge \
  && apt-get remove -y gcc rustc \
  && apt-get autoremove -y \
  && apt-get autoclean -y \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /usr/share/doc/*

COPY assets ./assets
COPY --from=dashboard-builder /build/TwitchChannelPointsMiner/dashboard/static ./TwitchChannelPointsMiner/dashboard/static
ENTRYPOINT [ "python", "run.py" ]
