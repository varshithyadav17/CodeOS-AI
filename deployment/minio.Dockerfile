# Local development only. Production repository archives belong in AWS S3.
# Build the official security release because community images are no longer distributed.
FROM golang:1.24.8-bookworm AS build
ENV CGO_ENABLED=0
WORKDIR /src
RUN git clone --depth 1 --branch RELEASE.2025-10-15T17-29-55Z https://github.com/minio/minio.git . \
    && go build -trimpath -o /out/minio . \
    && cp LICENSE /out/LICENSE \
    && cp NOTICE /out/NOTICE

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /out/LICENSE /out/NOTICE /usr/share/licenses/minio/
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
