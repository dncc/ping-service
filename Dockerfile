FROM python:3.7

# Install java and postgresql
RUN apt update \
    && apt install -y openjdk-11-jdk postgresql postgresql-contrib sudo vim \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY requirements.txt /tmp/requirements.txt
RUN pip install pip --upgrade --ignore-installed \
    && pip install -r /tmp/requirements.txt --upgrade \
    && rm -r /root/.cache/pip \
    && rm /tmp/requirements.txt

# Install zookeeper and kafka
RUN wget https://downloads.apache.org/kafka/2.4.1/kafka_2.13-2.4.1.tgz
RUN tar xzf kafka_2.13-2.4.1.tgz
RUN mv kafka_2.13-2.4.1 /opt/kafka
RUN rm kafka_2.13-2.4.1.tgz

COPY . /opt/ping-service/

ENV PYTHONPATH "/opt/ping-service/"

WORKDIR /opt/ping-service

ENTRYPOINT ["/opt/ping-service/entrypoint.sh"]
