FROM python:3.9

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

COPY . /app

WORKDIR /app

RUN pip install .

CMD exec nfhl-skid
