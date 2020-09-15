#!/usr/bin/env python3
"""
producer.py: create a Kafka producer to check a website availability by sending HTTP GET requests to it.
            Produce messages with HTTP GET: status code, response_time, time when it was send, and a flag
            signifying whether whether the content of the response was as expected.
Usage:
    src/producer.py run [options]

Options:
    -h --help                   show this screen.
    -e ENV --env=ENV   environment arg can be 'dev' or 'prod', default is 'dev'
"""
import re
import sys
import json
import jsonschema
import time
import kafka
import requests
from datetime import datetime
from docopt import docopt
try:
    from .config import get_config
    from .logger import get_logger
except ImportError:
    from config import get_config
    from logger import get_logger

logger = get_logger()


def create_producer(host, port, env='dev', **params):
    producer, error = None, None
    try:
        if env == 'dev':
            producer = kafka.KafkaProducer(bootstrap_servers=['{}:{}'.format(host, port)],
                                           value_serializer=lambda x: json.dumps(x).encode('utf-8'))
        elif env == 'prod':
            username, password = params['user'], params['password']
            security_protocol, ssl_cafile = params['security_protocol'], params['ssl_cafile']

            producer = kafka.KafkaProducer(bootstrap_servers='{}:{}'.format(host, port),
                                           sasl_mechanism="PLAIN",
                                           sasl_plain_password=password,
                                           sasl_plain_username=username,
                                           security_protocol="SASL_SSL",
                                           ssl_cafile=ssl_cafile,
                                           value_serializer=lambda x: json.dumps(x).encode('utf-8'))

    except (Exception, kafka.errors.NoBrokersAvailable) as err:
        logger.error(err)
        error = err

    return producer, error


def has_content(response, expected_content):
    resp_content = response.text
    match = re.search(expected_content, resp_content)

    return match is not None


def create_message(url, expected_content, response, schema):
    message = None
    try:
        message = {
            'url': url,
            'status_code': response.status_code,
            'timestamp': str(datetime.now()),
            'response_time': response.elapsed.total_seconds(),
            'has_content': has_content(response, expected_content)
        }
        jsonschema.validate(message, schema)

    except (Exception, json.decoder.JSONDecodeError) as error:
        logger.error(error)

    return message


def ping(url, expected_content, schema):
    response, error = None, None
    try:
        response = requests.get(url)
    except Exception as err:
        logger.error(err)
        error = err

    message = create_message(url, expected_content, response, schema)

    return message, error


def send_message(producer, data, topic):
    result, error = None, None
    try:
        result = producer.send(topic, value=data)
    except Exception as err:
        logger.error(err)
        error = err

    return result, error


def run(env):
    """
    Run kafka producer. Regularly check availability of a website and
    send the result to Kafka.
    """
    config = get_config('kafka', env)

    host = config.pop('host')
    port = config.pop('port')
    topic = config.pop('topic')
    schema = json.loads(config.pop('schema'))

    producer, err = create_producer(host, port, env, **config)
    if err:
        sys.exit()

    params = get_config('website', env)
    urls = json.loads(params['urls'])
    while True:
        for url, expected_content in urls:
            data, err = ping(url, expected_content, schema)
            if err:
                logger.warning("Abort sending {} to {} topic due to err: {}".format(data, topic, err))
                continue

            if data:
                logger.info("Sending {} to {} topic...".format(data, topic))
                send_message(producer, data, topic)
            else:
                logger.warning("Produced no data for {}, {} topic".format(url, topic))

        time.sleep(int(params['sleep']))


if __name__ == '__main__':
    logger = get_logger(add_console_handler=True)
    args = docopt(__doc__)
    env = args['--env'] if args['--env'] is not None else 'dev'
    run(env)
