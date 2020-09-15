import json
import kafka
import requests
import psycopg2
import testing.postgresql
import unittest
import jsonschema
import time
from datetime import datetime

import src.db as db
import src.config as config
import src.consumer as cons
import src.producer as prod


class PingServiceTest(unittest.TestCase):
    def setUp(self):
        kafka_config = config.get_config('kafka')
        self.host = kafka_config['host']
        self.port = kafka_config['port']
        self.topic = kafka_config['topic']
        self.schema = json.loads(kafka_config['schema'])

        web_config = config.get_config('website')
        self.urls = json.loads(web_config['urls'])
        self.url, self.expected_content = self.urls[0]
        self.waiting_time = 5  # seconds

        self.conn_pool, _ = db.create_conn_pool(env='dev')

    def test_create_producer(self):
        producer, error = prod.create_producer(self.host, self.port)
        self.assertEqual(error, None)
        self.assertTrue(producer is not None)
        self.assertEqual(type(producer), kafka.producer.kafka.KafkaProducer)

    def test_create_consumer(self):
        consumer, error = cons.create_consumer(self.topic, self.host, self.port)
        self.assertEqual(error, None)
        self.assertTrue(consumer is not None)
        self.assertEqual(type(consumer), kafka.consumer.group.KafkaConsumer)

    def test_send_and_receive_and_write_to_db(self):
        '''
        One monolithic test for sending, receiving and writing the message to DB
        as ordering of steps matters.
        '''

        # test sending
        producer, _ = prod.create_producer(self.host, self.port)

        data, error = prod.ping(self.url, self.expected_content, self.schema)
        self.assertEqual(error, None)
        self.assertTrue(data is not None)
        self.assertTrue(jsonschema.validate(data, self.schema) is None)

        result, error = prod.send_message(producer, data, self.topic)
        self.assertEqual(error, None)
        self.assertTrue(result is not None)

        count = 0
        while not result.is_done:
            time.sleep(1)
            count += 1
            if count < self.waiting_time:
                break
        self.assertTrue(result.succeeded())

        # test receiving
        consumer, _ = cons.create_consumer(topic=self.topic,
                                           host=self.host,
                                           port=self.port,
                                           auto_offset_reset='earliest',
                                           enable_auto_commit=True)

        msg = consumer.poll(timeout_ms=self.waiting_time * 2000, max_records=1)
        self.assertTrue(len(msg) > 0)
        item = msg.popitem()
        data = item[1][0].value
        self.assertTrue(jsonschema.validate(data, self.schema) is None)

        # test writing to db
        success, error = cons.write_to_db(data, consumer, self.conn_pool, self.schema)
        self.assertEqual(error, None)
        self.assertTrue(success)

        with self.conn_pool.getconn().cursor() as curs:
            url, status_code, timestamp = data['url'], data['status_code'], data['timestamp']
            curs.execute('''
                SELECT id, url FROM public.urls
                WHERE url='{url}'
            '''.format(url=url))
            rows = curs.fetchall()
            self.assertTrue(len(rows) == 1)
            uid, url = rows[0]

            curs.execute('''
                SELECT status_code, timestamp, response_time, has_content FROM public.pings
                WHERE url={uid}
                    AND status_code={status_code}
                    AND timestamp='{timestamp}'
            '''.format(uid=uid, status_code=status_code, timestamp=timestamp))
            rows = curs.fetchall()
            self.assertTrue(len(rows) == 1)


if __name__ == "__main__":
    unittest.main()
