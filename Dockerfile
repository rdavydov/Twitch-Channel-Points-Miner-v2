FROM python:3.12

ARG BUILDX_QEMU_ENV

WORKDIR /usr/src/app

COPY ./requirements.txt ./

ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

RUN pip install --upgrade pip

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -qq -y --fix-missing --no-install-recommends \
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
  && pip install -r requirements.txt \
  && pip cache purge \
  && apt-get remove -y gcc rustc \
  && apt-get autoremove -y \
  && apt-get autoclean -y \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /usr/share/doc/*

ADD ./TwitchChannelPointsMiner ./TwitchChannelPointsMiner
ENTRYPOINT [ "python", "run.py" ]
