FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install FFmpeg 7.x and dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    && add-apt-repository ppa:savoury1/ffmpeg7 \
    && apt-get update && apt-get install -y \
    ffmpeg \
    python3 \
    python3-pip \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY config.yaml .

# Configure Supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 8080

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
