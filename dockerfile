FROM python:3.9-slim

# Pré-requis pour transformers, numpy, onnxruntime, etc.
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Installer les librairies Python nécessaires
RUN pip3 install --upgrade pip && pip3 install \
    matplotlib \
    scikit-learn \
    sentence_transformers \
    transformers \
    onnxruntime \
    onnx \
    protobuf \
    accelerate \
    torch --extra-index-url https://download.pytorch.org/whl/cpu
    


# Copier ton code
COPY ./src /app
WORKDIR /app

ENTRYPOINT ["python3", "app.py"]
