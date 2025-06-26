#! /usr/bin/env bash

source .env

docker compose up -d && relay-service/print_amqp_url.sh
