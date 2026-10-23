# Runtime image: Docling (CPU-only torch) + models baked in + this package.
# The same image can later run unchanged on another host (e.g. Cloud Run Jobs).
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 app
USER app
ENV PATH=/home/app/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR /home/app

RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY --chown=app requirements.txt .
# TODO: pin the docling version once a first successful run confirms it works.
RUN pip install --no-cache-dir -r requirements.txt docling

# Download layout/table models at build time so runs don't fetch them again.
RUN docling-tools models download

COPY --chown=app docling_pipeline ./docling_pipeline

CMD ["python", "-m", "docling_pipeline.runner"]
