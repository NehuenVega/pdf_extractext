# Imagen con Vegeta (https://github.com/tsenart/vegeta), compilado desde el
# código fuente oficial en una versión fija: no hay imagen oficial en Docker
# Hub y así todos usamos exactamente el mismo binario.
FROM golang:1.27-alpine AS build
# Binario estático: no depende de las librerías de C de la imagen final.
ENV CGO_ENABLED=0
RUN go install github.com/tsenart/vegeta/v12@v12.13.0

FROM alpine:3.24
COPY --from=build /go/bin/vegeta /usr/local/bin/vegeta
ENTRYPOINT ["sh", "/stress/vegeta/run.sh"]
