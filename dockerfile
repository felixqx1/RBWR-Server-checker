FROM python:3.8-slim

WORKDIR /api-flask

COPY . .

RUN pip3 install --upgrade pip && pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["gunicorn", "main:app", "-b", "0.0.0.0:5000", "-w", "4"]