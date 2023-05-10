FROM python:3.9

WORKDIR /app

COPY requirements.txt .
#RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY ./python_stuff .

CMD ["python", "redis_v1.py"]