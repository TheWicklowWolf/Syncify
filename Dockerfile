FROM python:3.11-slim
# Create User
ARG UID=1000
ARG GID=1000
RUN groupadd -g $GID general_user && \
    useradd -m -u $UID -g $GID -s /bin/bash general_user
RUN umask 0000
# Install ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*
# Create directories and set permissions
COPY . /syncify
WORKDIR /syncify
RUN mkdir -p /syncify/downloads
RUN chown -R $UID:$GID /syncify
RUN chmod -R 777 /syncify/downloads
# Install requirements and run code as general_user
RUN pip install -r requirements.txt
EXPOSE 5000
USER general_user
CMD ["gunicorn","src.Syncify:app", "-c", "gunicorn_config.py"]
