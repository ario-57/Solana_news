FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY *.py ./
COPY .env.example .env.example

# Non-root user for security
RUN useradd -m botuser && chown -R botuser /app
USER botuser

CMD ["python", "bot.py"]
