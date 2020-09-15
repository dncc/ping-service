## ping-service

A simple website availability monitoring that relies on Aiven Kafka and PostgreSQL services, implemented in python.

The service consist of a Kafka producer and Kafka consumer instance. The Kafka producer periodically checks a target website, generates metrics about it (status code, response time etc.) and sends them to a dedicated topic. The Kafka consumer instance receives the producer's messages and stores them in PostgreSQL database.

### Development configuration
To change development configuration (params for kafka, postgresql, website etc.) edit: `src/settings.dev.conf` file.

### Build and run in dev. mode
To build and bring up a docker dev. image run:

```bash
    make build/ping run/dev &
```
To turn off writing of log messages to stdout, leaving only errors redirect the make output to /dev/null as follows:

```bash
    make run/dev 1>/dev/null &
```

### Run tests

To run unit tests within previously built docker image (`make build/ping`), run:
```bash
    make run/unittests
```

To run integration tests within previously built docker image (`make build/ping`), run:
```bash
    make run/integration
```

### Run with Aiven Kafka and PostgreSQL
To run with Aiven Cloud Database back-end, the service should be started as follows:

```bash
    PING_GPG_PASS=<gpg_password> make run/prod
```

where `<gpg_password>` is used to decrypt access credentials for already created (and running) Aiven Kafka and PostgreSQL services . The credentials are encrypted and saved in `secrets` directory, in this repo.





