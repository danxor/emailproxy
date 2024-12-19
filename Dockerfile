# syntax=docker/dockerfile:1
FROM python:slim

WORKDIR /app

# Setup folder for data-volume
RUN mkdir -p /app/data

# Copy application code
COPY requirements.txt .
COPY *.py .

# Install the requirements
RUN pip install -r requirements.txt

# Copy started script
COPY init.sh .

# Set command to run the application
CMD ["/bin/sh", "/app/init.sh"]
