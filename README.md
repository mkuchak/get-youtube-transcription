# YouTube Transcription API

A minimalistic Flask application that retrieves transcriptions from YouTube videos using a generic proxy configuration.

## Requirements
- Python 3.9+
- Docker (optional)

## Configuration

Create a `.env` file with your secret key:

```
SECRET_KEY=your_secret_key
```

The secret key must match the one used to encrypt the proxy strings on the client side.

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
docker run --env-file .env -p 6391:5000 youtube-transcript-api
```

3. The API will be available at: http://localhost:6391

## Running with Docker Compose (Recommended for Resilience)

1. Start the service:
```
docker-compose up -d

# Or do an entire rebuild
docker-compose up -d --build --force-recreate --no-deps
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
POST /transcript
Content-Type: application/json

{
    "videoId": "VIDEO_ID",
    "language": "en",  // optional, defaults to "en"
    "proxy": "ENCRYPTED_PROXY_STRING",  // optional
    "preserveFormatting": true  // optional, defaults to false
}
```

Parameters:
- `videoId`: The YouTube video ID (required)
- `language`: Specify a language code (e.g., 'en', 'es', 'fr') to get transcript in that language (defaults to 'en')
  - Note: This parameter only affects manual transcripts. Auto-generated transcripts are always returned in their original language.
- `proxy`: Encrypted proxy configuration string (encrypted using AES-GCM)
  - The proxy string should be encrypted before being sent to the API
  - The secret key must match the one configured in the server's environment variables
- `preserveFormatting`: Boolean flag to preserve HTML formatting elements such as `<i>` (italics) and `<b>` (bold) (defaults to false)

Examples:
```
# Get transcript in English (default) for manual transcripts
curl -X POST http://localhost:6391/transcript \
  -H "Content-Type: application/json" \
  -d '{"videoId": "VIDEO_ID"}'

# Get transcript specifically in Spanish for manual transcripts
curl -X POST http://localhost:6391/transcript \
  -H "Content-Type: application/json" \
  -d '{"videoId": "VIDEO_ID", "language": "es"}'

# Get transcript using an encrypted proxy
curl -X POST http://localhost:6391/transcript \
  -H "Content-Type: application/json" \
  -d '{"videoId": "VIDEO_ID", "proxy": "ENCRYPTED_PROXY_STRING"}'

# Get transcript with HTML formatting preserved
curl -X POST http://localhost:6391/transcript \
  -H "Content-Type: application/json" \
  -d '{"videoId": "VIDEO_ID", "preserveFormatting": true}'
```

Note: The proxy string must be encrypted using the same secret key configured in the server's environment variables. The encryption implementation uses AES-GCM with the following parameters:
- Key derivation: PBKDF2 with SHA-256
- Key length: 256 bits
- Iterations: 100,000
- Salt: "cloudflare-workers-salt"

### Transcript Prioritization System

The API tries to fetch transcripts in the following order of priority:

1. Manual (human-created) transcript in the requested language (default: English)
2. Auto-generated transcript in its original language (ignoring the language parameter)
3. Manual transcript in any language, translated to the requested language
4. Any available transcript in any language (as a fallback)
5. Last resort fallback to direct fetch with the requested language

The response includes additional metadata:
- `transcript`: The transcript data with timing information
- `language`: The language of the returned transcript 
- `is_generated`: Whether the transcript was auto-generated
- `translated`: Whether the transcript was translated from another language (for manual transcripts only)
- `original_language`: The original language before translation (if applicable)

This ensures you get the best available transcript quality for each video. The service is designed to always return a transcript if one is available in any language, rather than failing. 