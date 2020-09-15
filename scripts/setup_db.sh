#!/bin/bash

PG_DBNAME_DEV=$(grep dbname ${PWD}/src/settings.dev.conf | sed s/'dbname='/''/)
PG_USER_DEV=$(grep user ${PWD}/src/settings.dev.conf | sed s/'user='/''/)
PG_PASSWORD_DEV=$(grep password ${PWD}/src/settings.dev.conf | sed s/'password='/''/)
PG_TIMEZONE=$(grep timezone ${PWD}/src/settings.dev.conf | sed s/'timezone='/''/)

cat << EOF > setup.sql
    SET TIMEZONE TO '${PG_TIMEZONE}';
    DROP DATABASE IF EXISTS ${PG_DBNAME_DEV};
    CREATE DATABASE ${PG_DBNAME_DEV};
    DROP USER IF EXISTS ${PG_USER_DEV};
    CREATE USER ${PG_USER_DEV} WITH ENCRYPTED PASSWORD '${PG_PASSWORD_DEV}';
    GRANT ALL PRIVILEGES ON DATABASE ${PG_DBNAME_DEV} TO ${PG_USER_DEV};
EOF

sudo -u postgres psql -f setup.sql
rm setup.sql
