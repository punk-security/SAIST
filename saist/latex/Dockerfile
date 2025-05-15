FROM alpine:latest

ARG TL_MIRROR="https://texlive.info/CTAN/systems/texlive/tlnet"

RUN apk add --no-cache perl curl fontconfig libgcc gnupg python3 && \
    mkdir "/tmp/texlive" && cd "/tmp/texlive" && \
    wget "$TL_MIRROR/install-tl-unx.tar.gz" && \
    tar xzvf ./install-tl-unx.tar.gz && \
    ( \
        echo "selected_scheme scheme-minimal" && \
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

RUN tlmgr update --self

RUN tlmgr install scheme-basic && \
    tlmgr install scheme-small && \
    tlmgr install scheme-medium && \
    tlmgr install scheme-full

WORKDIR /app
COPY tex tex

ENTRYPOINT [ "latexmk" ]
CMD ["-pdf", "-outdir=out", "-auxdir=out/aux", "/app/report.tex"]