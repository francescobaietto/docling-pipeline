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
# TODO: pin the docling version once the pipeline is validated end to end.
RUN pip install --no-cache-dir -r requirements.txt docling

RUN docling-tools models download

COPY --chown=app docling_pipeline ./docling_pipeline

# Warm-up: convert a synthetic PDF once, so every model Docling really loads at
# runtime (layout, tables) is cached inside the image. OCR stays off.
RUN mkdir -p tests/fixtures
COPY --chown=app tests/__init__.py tests/make_fixture.py ./tests/
RUN python -m tests.make_fixture \
 && python -c "from docling_pipeline.converter import DoclingConverter; r = DoclingConverter(do_ocr=False).convert('tests/fixtures/sample_table.pdf'); print('warm-up ok, tables:', len(r.tables))" \
 && rm -rf tests

# From here on nothing may be downloaded at runtime: a missing model must fail loudly.
ENV HF_HUB_OFFLINE=1

CMD ["python", "-m", "docling_pipeline.runner"]
