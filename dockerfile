FROM python:3.14-slim

WORKDIR /root/

COPY . .

RUN pip3 install --upgrade pip && pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["python3", "main.py"]
#CMD ["gunicorn", "main:app", "-b", "0.0.0.0:5000", "-w", "4"]