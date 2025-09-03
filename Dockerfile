# Stage 1: Build the environment with all dependencies
# Use an official Python image that is based on the same OS as the NVIDIA image (Debian/Ubuntu family)
# This ensures system library compatibility.
FROM python:3.9-slim-bullseye AS builder

# Install system dependencies needed by OpenCV and PyQt5
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Set up a working directory
WORKDIR /app

# Upgrade pip and install Python libraries
# We install PyTorch first with its specific CUDA version
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------

# Stage 2: Create the final, smaller application image
# Use the official NVIDIA CUDA image as the final base for GPU support
FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC
# Critical for PyQt5 GUI apps in Docker
ENV QT_X11_NO_MITSHM=1

# Install only the RUNTIME system dependencies that match the ones from the builder stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for better security
RUN useradd -ms /bin/bash appuser
USER appuser
WORKDIR /home/appuser/app

# Copy the installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code
COPY . .

# Set the command to run when the container starts
ENTRYPOINT ["python", "main.py"]