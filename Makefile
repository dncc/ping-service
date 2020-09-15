PROJECT_DIR := $(shell basename `pwd`)
PROJECT_LOCAL_PATH := $(strip $(shell dirname "$(realpath $(lastword $(MAKEFILE_LIST)))"))

PG_DBNAME_DEV := $(shell grep dbname src/settings.dev.conf | sed s/'dbname='/''/)
PG_USER_DEV := $(shell grep user src/settings.dev.conf | sed s/'user='/''/)
PG_PASSWORD_DEV := $(shell grep password src/settings.dev.conf | sed s/'password='/''/)
PG_TIMEZONE := $(shell grep timezone src/settings.dev.conf | sed s/'timezone='/''/)

IMG_TAG ?= latest

.PHONY: build/ping
build/ping:
	sudo docker build . -t ${PROJECT_DIR}/ping:${IMG_TAG}

# ===== Run in development, production and test modes  ======
ping_docker_run = (sudo docker run -t --name ping-$1 \
				  -e POSTGRES_PASSWORD=${PG_PASSWORD_DEV} -e POSTGRES_USER=${PG_USER_DEV} \
				  -e POSTGRES_DBNAME=${PG_DBNAME_DEV} -e POSTGRES_TIMEZONE=${PG_TIMEZONE} \
				  ${PROJECT_DIR}/ping:${IMG_TAG} $1)

.PHONY: run/dev
run/dev:
	$(call ping_docker_run,dev)

.PHONY: run/prod
run/prod:
	PING_GPG_PASS=${PING_GPG_PASS} ${PWD}/scripts/create_prod_config.sh
	sudo docker build . -t ${PROJECT_DIR}/ping:${IMG_TAG}
	$(call ping_docker_run,prod)

.PHONY: test/unittest
test/unittest:
	$(call ping_docker_run,utest)
	docker rm -f ping-utest

.PHONY: test/integration
test/integration:
	$(call ping_docker_run,itest)
	docker rm -f ping-itest

# ================ DB Helpers =================
.PHONY: db/up
# Create development db
db/up:
	docker run -d --name ping-db -p 5432:5432 \
		-e POSTGRES_PASSWORD=${PG_PASSWORD_DEV} postgres:12-alpine
	echo "Setting up database ..."
	sleep 2
	PGPASSWORD=mysecretpassword psql -h localhost -U postgres -c "CREATE DATABASE ${PG_DBNAME_DEV};"
	PGPASSWORD=mysecretpassword psql -h localhost -U postgres -c \
		"CREATE USER kafka WITH ENCRYPTED PASSWORD '${PG_PASSWORD_DEV}'; \
		GRANT ALL PRIVILEGES ON DATABASE ping_service TO ${PG_USER_DEV};"

.PHONY: db/down
# Shutdown dev db
db/down:
	docker rm -f ping-db

.PHONY: db/connect
db/connect:
	PGPASSWORD=mysecretpassword psql -h localhost -U postgres

.PHONY: db/reset
# Reset db for dev
db/reset: db/down db/up

