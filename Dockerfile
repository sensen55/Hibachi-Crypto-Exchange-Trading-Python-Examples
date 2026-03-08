FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY hibachi_market.py .
COPY paper_trading.py .
COPY paper_main.py .
COPY nice_funks.py .
COPY main.py .

# State persistence directory
RUN mkdir -p /data
VOLUME /data

# Default environment
ENV PAPER_STATE_FILE=/data/paper_state.json
ENV HIBACHI_SYMBOL=BTC/USDT-P
ENV PAPER_BALANCE=10000
ENV POSITION_SIZE_USD=100
ENV LEVERAGE=2
ENV TAKE_PROFIT=2.0
ENV STOP_LOSS=-1.0
ENV LOOP_SLEEP=3
ENV BOT_MODE=long
ENV LOG_LEVEL=INFO

# Run paper trading bot
CMD ["python", "-u", "paper_main.py"]
