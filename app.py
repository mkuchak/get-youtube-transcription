from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.proxies import WebshareProxyConfig
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Get proxy credentials from environment variables
proxy_username = os.environ.get('WEBSHARE_USERNAME')
proxy_password = os.environ.get('WEBSHARE_PASSWORD')

# Configure YouTube Transcript API with proxy
ytt_api = YouTubeTranscriptApi(
    proxy_config=WebshareProxyConfig(
        proxy_username=proxy_username,
        proxy_password=proxy_password,
    ) if proxy_username and proxy_password else None
)

@app.route('/transcript', methods=['GET'])
def get_transcript():
    video_id = request.args.get('videoId')
    
    if not video_id:
        return jsonify({"error": "Missing videoId parameter"}), 400
    
    try:
        # Use the configured API instance
        transcript_list = ytt_api.get_transcript(video_id)
        return jsonify({"transcript": transcript_list})
    except NoTranscriptFound:
        return jsonify({"error": "No transcript found for this video"}), 404
    except VideoUnavailable:
        return jsonify({"error": "Video is unavailable"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
