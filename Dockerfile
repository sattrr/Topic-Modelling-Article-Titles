FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Jakarta

RUN apt-get update && \
    apt-get install -y \
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

RUN add-apt-repository ppa:deadsnakes/ppa && apt-get update

RUN apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3.10-distutils \
    python3-pip && \
    ln -sf /usr/bin/python3.10 /usr/bin/python3

RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3 && \
    python3 --version && pip --version

# Install Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && \
    apt-get install -y google-chrome-stable

# Install ChromeDriver using a more reliable method
RUN CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d '.' -f1-3) && \
    echo "Chrome version: $CHROME_VERSION" && \
    # Get the latest stable ChromeDriver version for this Chrome major version
    CHROME_MAJOR=$(echo $CHROME_VERSION | cut -d '.' -f1) && \
    echo "Chrome major version: $CHROME_MAJOR" && \
    # Try different approaches to get a working ChromeDriver
    if [ "$CHROME_MAJOR" -ge "115" ]; then \
        # For Chrome 115+, use Chrome for Testing API
        DRIVER_VERSION=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions.json" | jq -r '.channels.Stable.version') && \
        echo "Using ChromeDriver version: $DRIVER_VERSION" && \
        wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$DRIVER_VERSION/linux64/chromedriver-linux64.zip" && \
        unzip /tmp/chromedriver.zip -d /tmp/ && \
        mv /tmp/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver; \
    else \
        # For older Chrome versions, use the legacy method
        DRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_MAJOR") && \
        echo "Using ChromeDriver version: $DRIVER_VERSION" && \
        wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/$DRIVER_VERSION/chromedriver_linux64.zip" && \
        unzip /tmp/chromedriver.zip -d /tmp/ && \
        mv /tmp/chromedriver /usr/local/bin/chromedriver; \
    fi && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /tmp/chromedriver-linux64 /tmp/chromedriver && \
    # Verify installation
    chromedriver --version

WORKDIR /app
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]