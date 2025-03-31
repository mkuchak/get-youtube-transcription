# YouTube Transcription API

A minimalistic Flask application that retrieves transcriptions from YouTube videos.

## Requirements
- Python 3.9+
- Docker (optional)

## Installation and Running Locally

1. Install the dependencies:
```
pip install -r requirements.txt
```

2. Run the application:
```
python app.py
```

3. The API will be available at: http://localhost:5000

## Running with Docker

1. Build the Docker image:
```
docker build -t youtube-transcript-api .
```

2. Run the container:
```
docker run -p 6391:5000 youtube-transcript-api
```

3. The API will be available at: http://localhost:6391

## Running with Docker Compose (Recommended for Resilience)

1. Start the service:
```
docker-compose up -d
```

2. The API will be available at: http://localhost:6391

### Resilience Features

The Docker Compose configuration includes several features to ensure the service stays up:

- `restart: unless-stopped`: Automatically restarts the container if it crashes or if the server restarts
- Health checks: Monitors application health and restarts if it becomes unresponsive
- Resource limits: Prevents the container from consuming excessive resources

To make the service start automatically after server reboot:

```
# Enable Docker to start on boot
sudo systemctl enable docker

# Create a systemd service file for docker-compose
sudo nano /etc/systemd/system/youtube-transcript.service
```

Add the following content to the service file:

```
[Unit]
Description=YouTube Transcript API Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/your/app
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down

[Install]
WantedBy=multi-user.target
```

Then enable and start the service:

```
sudo systemctl enable youtube-transcript.service
sudo systemctl start youtube-transcript.service
```

## Usage

### Get a transcript
```
GET /transcript?videoId=VIDEO_ID
```

Example:
```
curl http://localhost:6391/transcript?videoId=VIDEO_ID
``` 