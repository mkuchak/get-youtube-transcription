from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, VideoUnavailable
import os

app = Flask(__name__)

@app.route('/transcript', methods=['GET'])
def get_transcript():
    video_id = request.args.get('videoId')
    
    if not video_id:
        return jsonify({"error": "Missing videoId parameter"}), 400
    
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
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