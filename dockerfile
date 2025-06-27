FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Install Python libraries
RUN pip3 install --no-cache-dir --upgrade pip && pip3 install --no-cache-dir \
    matplotlib \
    scikit-learn \
    sentence_transformers \
    transformers \
    onnxruntime \
    onnx \
    protobuf \
    accelerate \
    torch --extra-index-url https://download.pytorch.org/whl/cpu

# Copy application code
COPY ./src /app
WORKDIR /app

# Force unbuffered output for logs
ENTRYPOINT ["python3", "-u", "app.py"]
