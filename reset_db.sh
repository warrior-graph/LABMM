#!/usr/bin/env bash
set -e

echo "Removing existing database..."
rm -f instance/labhive.db

echo "Running migrations..."
flask db upgrade

echo "Seeding database..."
python seed.py

echo "Done."
