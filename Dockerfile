FROM python:3.11-slim

# System deps for scientific stack (numpy, scipy, h5py)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libhdf5-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python deps first (cache layer)
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir ".[web,cli]"

# Copy remaining files (data, etc.)
COPY data/ data/

# Default port
ENV PORT=8080
EXPOSE 8080

CMD ["patchagent-web"]
