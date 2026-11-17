FROM ubuntu:24.04

LABEL com.prodesign.protected="true" \
      com.prodesign.purpose="pd-one-ecrn-office-preview" \
      com.prodesign.cleanup-policy="do-not-prune"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      libreoffice-writer \
      libreoffice-calc \
      libreoffice-impress \
      libreoffice-draw \
      poppler-utils \
      python3 \
      python3-pil \
      fonts-noto-cjk \
      fonts-dejavu-core \
      fonts-liberation \
      ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

WORKDIR /skill
