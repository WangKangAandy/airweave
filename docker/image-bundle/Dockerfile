FROM registry.mthreads.com/cloud-mirror/ubuntu:20.04

WORKDIR /bundle

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends docker.io ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY airweave-base-images.tar /bundle/airweave-base-images.tar
COPY load.sh /usr/local/bin/load-bundled-images

RUN chmod +x /usr/local/bin/load-bundled-images

ENTRYPOINT ["/usr/local/bin/load-bundled-images"]
