import json
import jsonschema
import unittest
import kafka
import requests
import src.config as config
import src.consumer as cons
import src.producer as prod

from datetime import datetime
from collections import namedtuple

MockHttpResponse = namedtuple('HttpResponse', ['status_code', 'elapsed', 'text'])
NOHOST = 'no-url-yw8SLx4LB6e3r.OxO'
NOURL = "https://{s}/{s}".format(s=NOHOST)


class MockElapsed(object):
    def __init__(self, seconds):
        self.seconds = seconds

    def total_seconds(self):
        return self.seconds


def get_ok_response():
    return MockHttpResponse(
        200, MockElapsed(0.1), '''
        <!DOCTYPE html>                                                                                                                                                                                                    <html lang="en"> <head>
            <meta charset="utf-8">
          <link rel="dns-prefetch" href="https://github.githubassets.com">
          <link rel="dns-prefetch" href="https://avatars0.githubusercontent.com">
            ...
          <link rel="manifest" href="/manifest.json" crossOrigin="use-credentials">
          </head>
          <body class="logged-out env-production page-responsive f4">
            ...
             <p class="form-control-note text-center mt-6">
              By clicking &ldquo;Sign up for GitHub&rdquo;, you agree to our
              <a class="text-white" href="https://docs.github.com/terms" target="_blank">terms of service</a> and
              <a class="text-white" href="https://docs.github.com/privacy" target="_blank">privacy statement</a>. <span class="js-email-notice">We’ll occasionally send you account related emails.</span>
            </p>
            ...
          </body>
        </html>
        ''')


def get_error_response():
    return MockHttpResponse(
        500, MockElapsed(0.1), '''
        <!DOCTYPE html>                                                                                                                                                                                                    <html lang="en"> <head>
            <meta charset="utf-8">
            ...
          </head>
          <body>
          ...
             Woops!!!
          ...
          </body>
        </html>
        ''')


def get_nok_response():
    return MockHttpResponse(700, 0.1, '')


class TestKakfaProducer(unittest.TestCase):
    def setUp(self):
        kafka_config = config.get_config('kafka')
        self.host = kafka_config['host']
        self.port = kafka_config['port']
        self.topic = kafka_config['topic']
        self.schema = json.loads(kafka_config['schema'])

        web_config = config.get_config('website')
        self.url, self.expected_content = json.loads(web_config['urls'])[0]

    def test_create_producer_wo_broker(self):
        producer, error = prod.create_producer(NOHOST, 9999)
        self.assertTrue(producer is None)
        self.assertEqual(type(error), kafka.errors.NoBrokersAvailable)

    def test_has_content(self):
        ok_resp = get_ok_response()
        self.assertTrue(prod.has_content(ok_resp, self.expected_content))

        nok_resp = get_nok_response()
        self.assertTrue(not prod.has_content(nok_resp, self.expected_content))

    def test_create_message(self):
        def _test_msg_content(msg, resp, before, after):
            self.assertTrue(msg is not None)
            self.assertEqual(msg['url'], self.url)
            self.assertEqual(msg['status_code'], resp.status_code)
            self.assertEqual(msg['response_time'], resp.elapsed.total_seconds())
            timestamp = datetime.strptime(msg['timestamp'], '%Y-%m-%d %H:%M:%S.%f')
            self.assertTrue(before < timestamp)
            self.assertTrue(after > timestamp)

        ok_resp = get_ok_response()
        before = datetime.now()
        msg = prod.create_message(self.url, self.expected_content, ok_resp, self.schema)
        after = datetime.now()
        _test_msg_content(msg, ok_resp, before, after)

        err_resp = get_error_response()
        before = datetime.now()
        msg = prod.create_message(self.url, self.expected_content, err_resp, self.schema)
        after = datetime.now()
        _test_msg_content(msg, err_resp, before, after)

        nok_resp = get_nok_response()
        msg = prod.create_message(self.url, self.expected_content, nok_resp, self.schema)
        self.assertTrue(msg is None)

    def test_ping(self):
        data, err = prod.ping(self.url, self.expected_content, self.schema)
        self.assertTrue(err is None)
        self.assertTrue(data is not None)

        data, err = prod.ping(NOURL, self.expected_content, self.schema)
        self.assertEqual(type(err), requests.exceptions.ConnectionError)
        self.assertTrue(data is None)


class TestKakfaConsumer(unittest.TestCase):
    def setUp(self):
        kafka_config = config.get_config('kafka')
        self.host = kafka_config['host']
        self.port = kafka_config['port']
        self.topic = kafka_config['topic']
        self.schema = json.loads(kafka_config['schema'])

        web_config = config.get_config('website')
        self.url, self.expected_content = json.loads(web_config['urls'])[0]

    def test_create_consumer_wo_broker(self):
        consumer, error = cons.create_consumer(self.topic, NOHOST, 9999)
        self.assertTrue(consumer is None)
        self.assertEqual(type(error), kafka.errors.NoBrokersAvailable)

    def test_is_valid(self):
        is_valid = cons.is_valid(
            {
                'url': 'https://github.com',
                'status_code': 200,
                'timestamp': str(datetime.now()),
                'response_time': 0.1,
                'has_content': True
            }, self.schema)
        self.assertTrue(is_valid)

        is_valid = cons.is_valid(
            {
                'url': 'https://github.com',
                'status_code': 200,
                'timestamp': str(datetime.now()),
                'response_time': 0.1,
                'has_content': 'true'
            }, self.schema)
        self.assertTrue(not is_valid)
