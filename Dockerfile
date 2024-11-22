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

# Download the large CSV file from the public S3 bucket and store it in a specific directory
RUN mkdir -p /data
# Replace '[URL_to_your_S3_CSV]' with your actual S3 file URL
RUN wget -O /data/your_dataset.csv https://ship-density-data.s3.us-east-1.amazonaws.com/ship_density_data.csv

# Set environment variable for CSV file path
ENV CSV_FILE_PATH=/data/your_dataset.csv

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
# Install Python dependencies and Gunicorn
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt gunicorn

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["python", "main.py"]
