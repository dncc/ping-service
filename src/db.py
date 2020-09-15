#!/usr/bin/env python3
"""
src/db.py: setup a database and write a ping service results to it

Usage:
    db.py setup [options]
    db.py ping [options]

Options:
    -h --help                   show this screen.
    -e ENV --env=ENV   environment arg can be 'dev' or 'prod', default is 'dev'
    -d DOMAIN --domain=DOMAIN   website's domain.
    -u URLS --urls=URLS         CSV list of urls to send ping to.
"""
import json
import sys
import psycopg2
from psycopg2 import pool
from datetime import datetime
from docopt import docopt
try:
    from .config import get_config
    from .logger import get_logger
except ImportError:
    from config import get_config
    from logger import get_logger

STATUS_CODES = [(code, desc) for code, desc in sorted(get_config('status_codes').items())]

logger = get_logger()


def create_tables_sql():
    ''' create tables in the ping service database'''
    commands = ('''
        DROP TABLE IF EXISTS pings
        ''', '''
        DROP TABLE IF EXISTS urls
        ''', '''
        DROP TABLE IF EXISTS status_codes
        ''', '''
        CREATE TABLE urls(
           id INT GENERATED ALWAYS AS IDENTITY,
           domain VARCHAR(255) NOT NULL,
           url VARCHAR(255) NOT NULL UNIQUE,
           expected_content VARCHAR(255) NOT NULL,
           PRIMARY KEY(id)
        )
        ''', '''
        CREATE TABLE status_codes(
           status_code SMALLINT NOT NULL,
           description VARCHAR(255) DEFAULT '' NOT NULL,
           PRIMARY KEY(status_code)
        )
        ''', '''
        CREATE TABLE pings(
           url INT NOT NULL
           CONSTRAINT pings_url_foreign
           REFERENCES urls(id),
           status_code SMALLINT NOT NULL
           CONSTRAINT pings_status_code_foreign
           REFERENCES status_codes(status_code),
           timestamp TIMESTAMPTZ NOT NULL,
           /* response time is in seconds */
           response_time REAL NOT NULL,
           has_content BOOLEAN NOT NULL,
           PRIMARY KEY(url, status_code, timestamp)
        )
        ''')

    return commands


def populate_urls_sql(domain=None, urls=[]):
    '''
    Creates SQL commands to populate urls table.
   :param list urls: a list of lists, where each element list is a string pair:
                    ['<url>', '<expected_content>']
    '''

    if not urls:
        params = get_config('website')
        domain = params['domain']
        urls = json.loads(params['urls'])

    commands = tuple('''
        INSERT INTO urls(url, domain, expected_content)
        SELECT '{url}', '{domain}', '{content}'
        WHERE
            NOT EXISTS (
                SELECT url FROM urls WHERE url='{url}'
            )
        '''.format(url=url, domain=domain, content=content) for url, content in urls)

    return commands


def populate_status_codes_sql():
    command = '''
        INSERT INTO status_codes(status_code, description) VALUES(%s,%s)
        ON CONFLICT(status_code) DO NOTHING
    '''

    return command, STATUS_CODES


def get_conn_params(env):
    db_config = get_config('postgresql', env)

    return {
        'host': db_config['host'],
        'database': db_config['dbname'],
        'user': db_config['user'],
        'password': db_config['password'],
        'port': db_config['port']
    }


def create_db_connection(params, isolation_level=None):
    '''
    Read the connection parameters and create db connection
    '''
    conn = None
    try:
        conn = psycopg2.connect(**params)
        if conn:
            logger.info("Connection created successfully")
        if isolation_level is not None:
            conn.set_isolation_level(isolation_level)
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)

    return conn


def create_conn_pool(env):
    pool, error = None, None
    try:
        params = get_conn_params(env)
        pool = psycopg2.pool.SimpleConnectionPool(1, 10, **params)

        if pool:
            logger.info("Connection pool created successfully")
        else:
            raise psycopg2.DatabaseError

    except (Exception, psycopg2.DatabaseError) as err:
        logger.error(err)
        error = err

    return pool, error


def insert_ping_sql(url, status_code, timestamp, response_time, has_content):
    '''
    SQL commands to insert a ping result.
    First, insert its url and status_code if they don't exist already.
    Then, insert the ping result.
    '''

    commands = populate_urls_sql([url]) + (
        '''
        INSERT INTO status_codes(status_code)
        SELECT {status_code}
        WHERE
            NOT EXISTS (
                SELECT status_code FROM status_codes WHERE status_code={status_code}
            )
        '''.format(status_code=status_code),
        '''
        INSERT INTO pings(url, status_code, timestamp, response_time, has_content)
        VALUES (
            (SELECT id FROM urls WHERE url='{url}'),
            {status_code},
            '{timestamp}',
            {response_time},
            {has_content}
        )
        '''.format(
            url=url, status_code=status_code, timestamp=timestamp, response_time=response_time,
            has_content=has_content),
    )

    return commands


def execute_sql(commands, conn, close_conn=False):
    '''
    Execute sql commands, one by one and commit.
    '''
    try:
        with conn.cursor() as curs:
            for command in commands:
                curs.execute(command)
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
    finally:
        if conn is not None and close_conn:
            conn.close()

        return conn


def executemany_sql(command, values, conn, close_conn=False):
    '''
    Execute one sql command with many values and commit.
    '''
    try:
        with conn.cursor() as curs:
            curs.executemany(command, values)
        conn.commit()
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(error)
    finally:
        if conn is not None and close_conn:
            conn.close()

        return conn


if __name__ == '__main__':

    def _setup(env):
        '''
        A test method SQL commands that create and populate DB tables.
        Run with:

            $ scripts/setup_db.sh && python src/db.py setup

        '''
        conn = create_db_connection(get_conn_params(env))
        conn = execute_sql(create_tables_sql(), conn)
        conn = execute_sql(populate_urls_sql(), conn)
        executemany_sql(*populate_status_codes_sql(), conn, close_conn=True)

    def _ping(env, domain='', urls=''):
        '''
        A test method to check DB connection and insert queries.
        Run with:

            $ python src/db.py ping

        '''
        def _ping_ok_dummy(url):
            # return (status_code, timestamp, response_time, has_content)
            return (200, datetime.now(), 0.1, True)

        if domain and urls:
            urls = urls.replace(' ', '').split(',')
        else:
            params = get_config('website')
            domain = params['domain']
            urls = json.loads(params['urls'])

        conn = create_db_connection(get_conn_params(env))
        for url, _content in urls:
            data = _ping_ok_dummy(url)
            logger.info("Write ping results for {}".format(url))
            commands = insert_ping_sql(url, *data)
            conn = execute_sql(commands, conn)

        if conn is not None:
            conn.close()

    # main
    logger = get_logger(add_console_handler=True)
    args = docopt(__doc__)
    env = args['--env'] if args['--env'] is not None else 'dev'

    if args['setup']:
        _setup(env)

    elif args['ping']:
        _ping(env, args['--domain'], args['--urls'])
