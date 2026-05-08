FROM python:3.11

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860
EXPOSE 8000

CMD ["bash", "scripts/start.sh"]