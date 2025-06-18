FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Jakarta

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tzdata \
        software-properties-common \
        wget \
        curl \
        gnupg2 \
        ca-certificates \
        fonts-liberation \
        libappindicator3-1 \
        libasound2 \
        libx11-xcb1 \
        libxcomposite1 \
        libxrandr2 \
        libnss3 \
        libatk-bridge2.0-0 \
        libgtk-3-0 \
        xdg-utils \
        unzip \
        jq && \
    rm -rf /var/lib/apt/lists/*

# Install Python 3.10 and pip
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.10 \
        python3.10-venv \
        python3.10-distutils \
        python3-pip && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3 && \
    python3 --version && pip --version && \
    rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Install ChromeDriver
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f1-3) && \
    CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d '.' -f1) && \
    if [ "$CHROME_MAJOR" -ge "115" ]; then \
        DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json" | jq -r '.channels.Stable.version') && \
        wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$DRIVER_VERSION/linux64/chromedriver-linux64.zip" && \
        unzip /tmp/chromedriver.zip -d /tmp/ && \
        mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver; \
    else \
        DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR") && \
        wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$DRIVER_VERSION/chromedriver_linux64.zip" && \
        unzip /tmp/chromedriver.zip -d /tmp/ && \
        mv /tmp/chromedriver /usr/local/bin/chromedriver; \
    fi && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64 /tmp/chromedriver

WORKDIR /app

COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]