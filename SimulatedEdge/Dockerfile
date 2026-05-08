FROM python:3.11-slim

# Prevent Python from buffering stdout
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

CMD ["python","-m", "App"]