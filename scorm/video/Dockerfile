# Toolbox used to render the phishing awareness video (frames + French TTS + encode).
FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      ffmpeg python3 python3-pil python3-venv fonts-dejavu-core ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv /opt/piper && /opt/piper/bin/pip install --no-cache-dir piper-tts
RUN mkdir -p /voices && cd /voices \
    && base=https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium \
    && curl -fsSLO $base/fr_FR-siwis-medium.onnx \
    && curl -fsSLO $base/fr_FR-siwis-medium.onnx.json
WORKDIR /work
