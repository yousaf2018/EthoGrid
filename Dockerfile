# ---------- Base image with Conda ----------
FROM continuumio/miniconda3:latest

# Avoid prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install GUI dependencies (Qt/X11)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libxext6 \
    libsm6 \
    libxrender1 \
    x11-apps \
    && rm -rf /var/lib/apt/lists/*

# ---------- Create environment ----------
RUN conda create -n ethogrid-env python=3.10 -y

# Use conda environment
SHELL ["conda", "run", "-n", "ethogrid-env", "/bin/bash", "-c"]

# Install conda packages (Qt-safe stack)
RUN conda install -c conda-forge \
    opencv \
    pyqt \
    qt \
    numpy \
    pandas \
    matplotlib \
    seaborn \
    pillow \
    scipy \
    openpyxl \
    -y

# Install pip packages
RUN pip install \
    ultralytics \
    filterpy \
    nofair \
    pyinstaller \
    pyinstaller-hooks-contrib

# ---------- Copy EthoGrid app ----------
WORKDIR /app
COPY . /app

# ---------- Default command ----------
CMD ["conda", "run", "--no-capture-output", "-n", "ethogrid-env", "python", "main.py"]
