FROM python:3.12-alpine as builder

# Create app directory
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-alpine AS saist
RUN apk update && apk add git
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN mkdir -p /app/results
WORKDIR /app

COPY saist .

# Exports
ENV SAIST_COMMAND "docker run punksecurity/saist" 
ENV SAIST_CSV_PATH "/app/results.csv" 
ENV SAIST_LATEX_PATH "/app/report.tex"
ENV SAIST_WEB_HOST "0.0.0.0"
ENV PYTHONUNBUFFERED 1
ENTRYPOINT [ "python3", "/app/main.py" ]
CMD [ "-h" ]

FROM saist as saist-tex

ARG TL_MIRROR="https://texlive.info/CTAN/systems/texlive/tlnet"
ARG TL_PACKAGES="lineno titlesec upquote minted blindtext booktabs fontawesome latexmk parskip xcolor"

RUN apk add --no-cache perl curl fontconfig python3 && \
    mkdir "/tmp/texlive" && cd "/tmp/texlive" && \
    wget "$TL_MIRROR/install-tl-unx.tar.gz" && \
    tar xzvf ./install-tl-unx.tar.gz && \
    ( \
        echo "selected_scheme scheme-basic" && \
        echo "instopt_adjustpath 0" && \
        echo "tlpdbopt_install_docfiles 0" && \
        echo "tlpdbopt_install_srcfiles 0" && \
        echo "TEXDIR /opt/texlive/" && \
        echo "TEXMFLOCAL /opt/texlive/texmf-local" && \
        echo "TEXMFSYSCONFIG /opt/texlive/texmf-config" && \
        echo "TEXMFSYSVAR /opt/texlive/texmf-var" && \
        echo "TEXMFHOME ~/.texmf" \
    ) > "/tmp/texlive.profile" && \
    "./install-tl-"*"/install-tl" --location "$TL_MIRROR" -profile "/tmp/texlive.profile" && \
    rm -vf "/opt/texlive/install-tl" && \
    rm -vf "/opt/texlive/install-tl.log" && \
    rm -vrf /tmp/*

ENV PATH="${PATH}:/opt/texlive/bin/x86_64-linuxmusl"

RUN tlmgr update --self && \
    tlmgr install ${TL_PACKAGES}
