# Use a base image with Python 3.8
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for GDAL and general build process
RUN apt-get update && apt-get install -y \
    build-essential \
    libgdal-dev \
    gdal-bin \
    gcc \
    g++ \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set GDAL environment variables
ENV GDAL_CONFIG=/usr/bin/gdal-config
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

# Download the large CSV file from S3 and store it in a specific directory
RUN mkdir -p /data
RUN wget -O /data/your_dataset.csv [URL_to_your_S3_CSV]

# Set environment variable for CSV file path
ENV CSV_FILE_PATH=/data/your_dataset.csv

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Expose the port the app runs on
EXPOSE 5000

# Run the application
CMD ["python", "main.py"]
