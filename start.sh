#!/bin/bash
gunicorn -p 8000 app:app & python3 ./main.py