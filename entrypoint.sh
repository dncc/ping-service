#!/bin/bash
set -e

if [ $1 == "utest" ]; then
    sudo useradd -m -d /home/unittests unittests
    echo "Running db unit tests ..."
    su - unittests -c 'cd /opt/ping-service && python -m unittest tests/test_db.py'
    echo "Running kafka unit tests ..."
    su - unittests -c 'cd /opt/ping-service && python -m unittest tests/test_kafka.py'

elif [ $1 == "prod" ]; then
    echo "Starting kafka producer..."
    PYTHONPATH=/opt/ping-service python src/producer.py run --env prod &

    echo "Starting kafka consumer..."
    PYTHONPATH=/opt/ping-service python src/consumer.py run --env prod

else
    echo "Starting kafka ... "

    # Start Kafka And ZooKeeper Server in the background (without creating systemd unit file)
    sudo nohup /opt/kafka/bin/zookeeper-server-start.sh \
        -daemon /opt/kafka/config/zookeeper.properties > /dev/null 2>&1 &
    sleep 2
    sudo nohup /opt/kafka/bin/kafka-server-start.sh \
        -daemon /opt/kafka/config/server.properties > /dev/null 2>&1 &
    sleep 2

    cd /opt/ping-service

    echo "Setting up database ..."
    service postgresql start

cat << EOF > setup.sql
    SET TIMEZONE TO '${POSTGRES_TIMEZONE}';
    CREATE DATABASE ${POSTGRES_DBNAME};
    CREATE USER ${POSTGRES_USER} WITH ENCRYPTED PASSWORD '${POSTGRES_PASSWORD}';
    GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DBNAME} TO ${POSTGRES_USER};
EOF
    sudo -u postgres psql -f setup.sql
    python src/db.py setup

    if [ $1 == "itest" ]; then
        echo "Running integration tests ..."
        PYTHONPATH=/opt/ping-service python tests/integration_test.py

    elif [ $1 == "dev" ]; then
        echo "Running in dev mode..."
        echo "Starting kafka producer..."
        PYTHONPATH=/opt/ping-service python src/producer.py run &

        echo "Starting kafka consumer..."
        PYTHONPATH=/opt/ping-service python src/consumer.py run

    else
        echo "Unknown parameter: $1"
    fi
fi


