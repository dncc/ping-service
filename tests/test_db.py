import json
import psycopg2
import testing.postgresql
import unittest
from datetime import datetime

import src.db as db
import src.config as config
'''
 Inspired by:
    https://github.com/walkermatt/python-postgres-testing-demo
    https://docs.python.org/3/library/unittest.html

# TODO test against a database state(s) defined by fixures/<state>.sql
'''


class TestDB(unittest.TestCase):
    def setUp(self):
        """
        Creates a temporary database, a database connection to it and
        database parameters.
        """
        # Reference to testing.postgresql database instance
        self.db_instance = testing.postgresql.Postgresql()
        # DB connection parameters (host, port etc.) which can be passed to the functions being tested
        self.conn_params = self.db_instance.dsn()
        # Connection to the database used to set the database state before running each test
        self.db_conn = psycopg2.connect(**self.conn_params)

    def tearDown(self):
        """
        After all of the tests in this file have been executed close
        the database connection and destroy the temporary database.
        """
        self.db_conn.close()
        self.db_instance.stop()

    def test_create_db_connection(self):
        test_conn = db.create_db_connection(self.conn_params)
        self.assertTrue(test_conn is not None)

        test_params = test_conn.info.dsn_parameters
        param_names = zip(['dbname', 'host', 'port', 'user'], ['database', 'host', 'port', 'user'])
        for l, r in param_names:
            self.assertEqual(test_params[l], str(self.conn_params[r]))

    def test_create_tables(self):
        db.execute_sql(db.create_tables_sql(), self.db_conn)

        with self.db_conn.cursor() as curs:
            curs.execute('''
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema='public' AND table_catalog='test'
                ''')
            tables = set([res[0] for res in curs.fetchall()])
            self.assertEqual(tables, {'pings', 'status_codes', 'urls'})

    def test_populate_urls(self):
        params = config.get_config('website')
        expected_domain = params['domain']
        expected_urls = json.loads(params['urls'])

        db.execute_sql(db.create_tables_sql(), self.db_conn)
        db.execute_sql(db.populate_urls_sql(), self.db_conn)
        with self.db_conn.cursor() as curs:
            curs.execute("SELECT domain, url, expected_content FROM public.urls")
            rows = curs.fetchall()
            self.assertEqual(rows[0][0], expected_domain)
            self.assertEqual([[r[1], r[2]] for r in rows], expected_urls)

    def test_populate_status_codes(self):
        expected_rows = [(int(code), desc) for code, desc in sorted(config.get_config('status_codes').items())]

        db.execute_sql(db.create_tables_sql(), self.db_conn)
        db.executemany_sql(*db.populate_status_codes_sql(), self.db_conn)
        with self.db_conn.cursor() as curs:
            curs.execute("SELECT * FROM public.status_codes")
            rows = curs.fetchall()
            self.assertEqual(rows, expected_rows)

    def test_insert_ping_results(self):
        def _ping_ok_dummy(url):
            return (200, datetime.now(), 0.1, True)

        def _ping_nok_dummy(url):
            return (700, datetime.now(), 0.2, False)

        def _test_status_code(status_code, curs):
            curs.execute('''
                SELECT status_code FROM public.status_codes
                WHERE status_code={status_code}
            '''.format(status_code=status_code))
            rows = curs.fetchall()
            # make sure status codes are unique (written only once)
            self.assertTrue(len(rows) == 1)
            self.assertEqual(rows[0][0], status_code)

            return rows[0][0]

        def _test_url(url, curs):
            curs.execute('''
                SELECT id, url FROM public.urls
                WHERE url='{url}'
            '''.format(url=url))

            rows = curs.fetchall()
            # make sure urls are unique (written only once)
            self.assertTrue(len(rows) == 1)
            uid, url = rows[0]
            self.assertEqual(url, url)

            return uid

        def _test_ping(uid, status_code, timestamp, curs, expected):
            curs.execute('''
                SELECT status_code, timestamp, response_time, has_content FROM public.pings
                WHERE url={uid}
                    AND status_code={status_code}
                    AND timestamp='{timestamp}'
            '''.format(uid=uid, status_code=status_code, timestamp=timestamp))

            rows = curs.fetchall()
            self.assertTrue(len(rows) == 1)
            r = rows[0]
            self.assertEqual((r[0], r[1].replace(tzinfo=None), r[2], r[3]), expected)

        db.execute_sql(db.create_tables_sql(), self.db_conn)
        db.execute_sql(db.populate_urls_sql(), self.db_conn)
        db.executemany_sql(*db.populate_status_codes_sql(), self.db_conn)

        params = config.get_config('website')
        domain = params['domain']
        urls = json.loads(params['urls'])
        for url, _content in urls:
            ok_row = _ping_ok_dummy(url)
            commands_ok = db.insert_ping_sql(url, *ok_row)
            db.execute_sql(commands_ok, self.db_conn)

            nok_row = _ping_nok_dummy(url)
            commands_nok = db.insert_ping_sql(url, *nok_row)
            db.execute_sql(commands_nok, self.db_conn)

            with self.db_conn.cursor() as curs:
                uid = _test_url(url, curs)

                status_code, timestamp = ok_row[0], ok_row[1]
                _test_status_code(status_code, curs)
                _test_ping(uid, status_code, timestamp, curs, ok_row)

                status_code, timestamp = nok_row[0], nok_row[1]
                _test_status_code(status_code, curs)
                _test_ping(uid, status_code, timestamp, curs, nok_row)


if __name__ == '__main__':
    unittest.main()
