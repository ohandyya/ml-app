# lambda/Dockerfile

FROM python:3.8

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT [ "/usr/local/bin/python", "-m", "awslambdaric" ]

CMD ["prediction.handler"]
