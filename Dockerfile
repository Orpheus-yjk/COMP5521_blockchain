FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD ["python", "client_bash.py", "--port", "5000", "--api-port", "5001"]