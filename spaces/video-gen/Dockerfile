FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PATH="/home/user/.local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    git \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user
WORKDIR $HOME/app

COPY --chown=user:user requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Download DWPose onnx models pre-cached
RUN mkdir -p $HOME/app/models/dwpose && \
    curl -L -o $HOME/app/models/dwpose/dw-ll_ucoco_384.onnx https://huggingface.co/yisol/ID-Animator/resolve/main/models/DWPose/dw-ll_ucoco_384.onnx || true

COPY --chown=user:user . .

EXPOSE 7860
CMD ["python3", "app.py"]
