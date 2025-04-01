from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, VideoUnavailable
from youtube_transcript_api.proxies import GenericProxyConfig
from dotenv import load_dotenv
import os
import sys
import re
from encryption import decrypt

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Force stdout to be line-buffered for Docker logs
sys.stdout.reconfigure(line_buffering=True)

def parse_proxy_string(proxy_string):
    """Parse proxy string in format 'username:password@hostname:port'"""
    if not proxy_string:
        return None
        
    # Basic validation of proxy string format
    pattern = r'^([^:]+):([^@]+)@([^:]+):(\d+)$'
    match = re.match(pattern, proxy_string)
    if not match:
        return None
        
    username, password, host, port = match.groups()
    return {
        'username': username,
        'password': password,
        'host': host,
        'port': port
    }

@app.route('/transcript', methods=['POST'])
def get_transcript():
    # Get data from JSON body
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
        
    video_id = data.get('videoId')
    language = data.get('language', 'en')  # Default to English if not specified
    encrypted_proxy = data.get('proxy')  # Encrypted proxy string
    secret_key = os.environ.get('SECRET_KEY')  # Get secret key from environment
    
    if not video_id:
        return jsonify({"error": "Missing videoId in request body"}), 400
    
    print(f"Requested videoId: {video_id}, language: {language}")
    sys.stdout.flush()
    
    try:
        # Configure proxy if provided
        proxy_config = None
        if encrypted_proxy:
            if not secret_key:
                return jsonify({"error": "Secret key not configured"}), 500
                
            # Decrypt the proxy string
            proxy_string = decrypt(encrypted_proxy, secret_key)
            if not proxy_string:
                return jsonify({"error": "Failed to decrypt proxy string"}), 400
                
            proxy_parts = parse_proxy_string(proxy_string)
            if proxy_parts:
                proxy_config = GenericProxyConfig(
                    http_url=f"http://{proxy_parts['username']}:{proxy_parts['password']}@{proxy_parts['host']}:{proxy_parts['port']}",
                    https_url=f"http://{proxy_parts['username']}:{proxy_parts['password']}@{proxy_parts['host']}:{proxy_parts['port']}"
                )
                print(f"Using proxy configuration for request")
                sys.stdout.flush()
            else:
                return jsonify({"error": "Invalid proxy string format. Expected format: username:password@hostname:port"}), 400
        
        # Create YouTubeTranscriptApi instance with proxy config
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
        
        # Try to get all available transcripts
        available_transcripts = ytt_api.list_transcripts(video_id)
        
        # Log available languages
        languages = [{"language": t.language_code, "is_generated": t.is_generated} for t in available_transcripts]
        print(f"Available languages for {video_id}: {languages}")
        sys.stdout.flush()
        
        # First priority: Try to get manual transcript in requested language (default: English)
        try:
            # Check if manual transcript exists in the requested language
            for transcript in available_transcripts:
                if transcript.language_code == language and not transcript.is_generated:
                    print(f"Found manual transcript in {language}")
                    sys.stdout.flush()
                    transcript_data = transcript.fetch()
                    return jsonify({
                        "transcript": transcript_data, 
                        "language": language,
                        "is_generated": False
                    })
        except Exception as e:
            print(f"Error finding manual transcript in {language}: {str(e)}")
            sys.stdout.flush()
            
        # Second priority: Try to get ANY generated transcript in its original language
        try:
            for transcript in available_transcripts:
                if transcript.is_generated:
                    original_language = transcript.language_code
                    print(f"Found generated transcript in original language {original_language}")
                    sys.stdout.flush()
                    transcript_data = transcript.fetch()
                    return jsonify({
                        "transcript": transcript_data, 
                        "language": original_language, 
                        "is_generated": True
                    })
        except Exception as e:
            print(f"Error finding generated transcript: {str(e)}")
            sys.stdout.flush()
            
        # Third priority: Try to get ANY manual transcript and translate it to requested language
        try:
            for transcript in available_transcripts:
                if not transcript.is_generated:
                    print(f"Found manual transcript in {transcript.language_code}, translating to {language}")
                    sys.stdout.flush()
                    translated = transcript.translate(language)
                    transcript_data = translated.fetch()
                    return jsonify({
                        "transcript": transcript_data, 
                        "language": language, 
                        "original_language": transcript.language_code,
                        "translated": True,
                        "is_generated": False
                    })
        except Exception as e:
            print(f"Error translating manual transcript: {str(e)}")
            sys.stdout.flush()
        
        # Last resort: Try the original method
        try:
            transcript_list = ytt_api.get_transcript(video_id, languages=[language])
            return jsonify({"transcript": transcript_list, "language": language})
        except Exception as e:
            print(f"Error using original method: {str(e)}")
            sys.stdout.flush()
            
        # If we got this far, we've tried everything and failed
        return jsonify({"error": "No transcript found for this video after multiple attempts"}), 404
            
    except VideoUnavailable:
        print(f"Video unavailable: {video_id}")
        sys.stdout.flush()
        return jsonify({"error": "Video is unavailable"}), 404
    
    except Exception as e:
        print(f"Error processing video {video_id}: {str(e)}")
        sys.stdout.flush()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on port {port}")
    sys.stdout.flush()
    app.run(host='0.0.0.0', port=port)
