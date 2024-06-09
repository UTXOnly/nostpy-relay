FROM python:3.11-slim

# Update package lists and install necessary dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        pkg-config \
        libc-dev \
        g++ \
        make \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy requirements file and install dependencies
COPY eh_requirements.txt .
RUN pip install --no-cache-dir -r eh_requirements.txt

# Copy application code
COPY . .
#"opentelemetry-instrument",
# Instrument the application with OpenTelemetry and set the command to run the application
CMD [ "python", "event_handler.py"]

