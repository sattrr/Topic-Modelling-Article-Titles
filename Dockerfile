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
    unzip && \
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

RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt . 
RUN python3 -m pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]