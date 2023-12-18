#!/usr/bin/env sh

# shut down containers if running
podman-compose -f dev.yml down

# start up containers
podman-compose -f dev.yml up -d

# remove venv
poetry env remove --all

# install runtime and dev dependencies as defined in lockfile
poetry install --with dev --sync

# generate manifest file
poetry run ./scripts/create-manifest.py

# run db migration
FLASK_APP=system_baseline.app:get_flask_app_with_migration poetry run flask db upgrade

# check that the db, migration and models are up to date with each other
poetry run alembic --raiseerr --config migrations/alembic.ini check

# run unit tests
poetry run ./run_unit_tests.sh

# shut down containers
podman-compose -f dev.yml down
