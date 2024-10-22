# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Install Gunicorn
RUN pip install gunicorn

# Copy the rest of the application code
COPY . .

# Copy the Google Cloud service account key
COPY voiceinteractionapp-436602-64413c96f909.json /app/

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Set the environment variable for Flask
ENV FLASK_APP=main.py

# Run the application using Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]