FROM alpine:3.19

# Pre-install tooling required by init-vespa.sh so runtime does not depend on apk network.
RUN apk add --no-cache curl zip

WORKDIR /work
