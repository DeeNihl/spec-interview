FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPEC_INTERVIEW_DATA_DIR=/data/sessions

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN useradd --create-home --uid 10001 appuser && mkdir -p /data/sessions \
    && chown -R appuser:appuser /data
USER appuser

VOLUME ["/data/sessions"]
ENTRYPOINT ["spec-interview"]
CMD ["--help"]

