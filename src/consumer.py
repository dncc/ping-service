#!/usr/bin/env python3
"""
consumer.py: create a Kafka consumer to receive ping messages and write them to postgres database.

Usage:
    src/consumer.py run [options]

Options:
    -h --help show this screen.
    -e ENV --env=ENV environment arg can be 'dev' or 'prod', default is 'dev'
"""
import sys
import json
import jsonschema
import kafka
import psycopg2
from docopt import docopt
try:
    from .config import get_config
    from .logger import get_logger
    from .db import create_conn_pool, insert_ping_sql, execute_sql
except ImportError:
    from config import get_config
    from logger import get_logger
    from db import create_conn_pool, insert_ping_sql, execute_sql

logger = get_logger()


def create_consumer(topic, host, port, env='dev', auto_offset_reset='latest', enable_auto_commit=False, **params):
    '''
    Create a consumer that picks up the latest message not committed message after
    restart. For this behavior 'auto_offset_reset' and  'able_auto_commit' should
    be set to 'latest' and False, respectively.
    '''

    consumer, error = None, None
    try:
        if env == 'dev':
            consumer = kafka.KafkaConsumer(topic,
                                           bootstrap_servers=['{}:{}'.format(host, port)],
                                           auto_offset_reset=auto_offset_reset,
                                           enable_auto_commit=enable_auto_commit,
                                           group_id='ping-group',
                                           value_deserializer=lambda x: json.loads(x.decode('utf-8')))
        elif env == 'prod':
            username, password = params['user'], params['password']
            security_protocol, ssl_cafile = params['security_protocol'], params['ssl_cafile']

            consumer = kafka.KafkaConsumer(topic,
                                           bootstrap_servers='{}:{}'.format(host, port),
                                           auto_offset_reset=auto_offset_reset,
                                           enable_auto_commit=enable_auto_commit,
                                           group_id='ping-group',
                                           sasl_mechanism="PLAIN",
                                           sasl_plain_username=username,
                                           sasl_plain_password=password,
                                           security_protocol="SASL_SSL",
                                           ssl_cafile=ssl_cafile,
                                           value_deserializer=lambda x: json.loads(x.decode('utf-8')))

    except Exception as err:
        logger.error(err)
        error = err

    return consumer, error


def is_valid(data, schema):
    valid = True
    try:
        jsonschema.validate(data, schema)

    except (Exception, json.decoder.JSONDecodeError) as error:
        logger.error(error)
        valid = False

    return valid


def write_to_db(data, consumer, conn_pool, schema):
    success, error = True, None
    if not is_valid(data, schema):
        success = False
        error = Exception('Invalid data {}'.format(data))
        return success, error

    commands = insert_ping_sql(**data)
    conn = None
    try:
        conn = conn_pool.getconn()
        conn = execute_sql(commands, conn)
        consumer.commit()
    except Exception as err:
        logger.error(error)
        success, error = False, err
    finally:
        if conn:
            conn_pool.putconn(conn)

    return success, error


def run(env):
    """
    Run kafka consumer. Receive ping service data and write it to PosgreSQL db.
    """
    config = get_config('kafka', env)

    host = config.pop('host')
    port = config.pop('port')
    topic = config.pop('topic')
    schema = json.loads(config.pop('schema'))

    consumer, err = create_consumer(topic, host, port, env, **config)
    if err:
        sys.exit()

    conn_pool, err = create_conn_pool(env)
    if err:
        sys.exit()

    try:
        logger.info("Get {} messages ...".format(topic))
        for message in consumer:
            data = message.value
            logger.info("Received: {}, writing to postgres...".format(data))
            write_to_db(data, consumer, conn_pool, schema)

    except Exception as error:
        logger.error(error)
    finally:
        # closing all active database connections
        if conn_pool:
            conn_pool.closeall()
        logger.info("PostgreSQL connection pool is closed")


if __name__ == '__main__':
    logger = get_logger(add_console_handler=True)
    args = docopt(__doc__)
    env = args['--env'] if args['--env'] is not None else 'dev'
    run(env)
