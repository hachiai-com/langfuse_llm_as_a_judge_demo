FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command - can be overridden when running the container
# To run the app interactively: docker compose run app python main.py
CMD ["tail", "-f", "/dev/null"]

