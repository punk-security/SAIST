FROM python:3.13-alpine AS builder

# Create app directory
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13-alpine AS saist
RUN apk update && apk add git
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir -p /app/results
WORKDIR /app

COPY saist .

# Exports
ENV SAIST_COMMAND "docker run punksecurity/saist" 
ENV SAIST_CSV_PATH "/app/results.csv" 
ENV SAIST_TEX_FILENAME "report.tex"
ENV SAIST_PDF_FILENAME "report.pdf"
ENV SAIST_WEB_HOST "0.0.0.0"
ENV PYTHONUNBUFFERED 1
ENTRYPOINT [ "python3", "/app/main.py" ]
CMD [ "-h" ]

FROM saist AS saist-tex

ARG TL_MIRROR="https://texlive.info/CTAN/systems/texlive/tlnet"

COPY saist/latex/texlive.profile /tmp

RUN apk add --no-cache perl curl fontconfig && \
    mkdir "/tmp/texlive" && cd "/tmp/texlive" && \
    wget "$TL_MIRROR/install-tl-unx.tar.gz" && \
    tar xzvf ./install-tl-unx.tar.gz && \
    "./install-tl-"*"/install-tl" --location "$TL_MIRROR" -profile "/tmp/texlive.profile" && \
    rm -vf "/opt/texlive/install-tl" && \
    rm -vf "/opt/texlive/install-tl.log" && \
    rm -vrf /tmp/* \

ARG BUILDARCH="x86_64"
ENV PATH="${PATH}:/opt/texlive/bin/${BUILDARCH:-x86_64}-linuxmusl"

ARG TL_PACKAGES="lineno titlesec upquote minted blindtext booktabs fontawesome latexmk parskip xcolor"

RUN tlmgr update --self && \
    tlmgr install ${TL_PACKAGES}
