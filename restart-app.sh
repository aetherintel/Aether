#!/bin/bash

# Restart frontend and backend services
docker compose --env-file .env.dev up -d --build backend frontend
