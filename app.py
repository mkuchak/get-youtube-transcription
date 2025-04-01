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

def convert_transcript_to_json(transcript):
    """Convert a FetchedTranscript object to JSON-serializable format"""
    # Convert each snippet to a dictionary
    snippets = []
    for snippet in transcript.snippets:
        snippets.append({
            'text': snippet.text,
            'start': snippet.start,
            'duration': snippet.duration
        })
    return snippets

@app.route('/transcript', methods=['POST'])
def get_transcript():
    # Get data from JSON body
    data = request.get_json()
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400
        
    video_id = data.get('videoId')
    language = data.get('language', 'en')  # Default to English if not specified
    encrypted_proxy = data.get('proxy')  # Encrypted proxy string
    preserve_formatting = data.get('preserveFormatting', False)  # Whether to preserve HTML formatting
    secret_key = os.environ.get('SECRET_KEY')  # Get secret key from environment
    
    if not video_id:
        return jsonify({"error": "Missing videoId in request body"}), 400
    
    print(f"Requested videoId: {video_id}, language: {language}, preserve_formatting: {preserve_formatting}")
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
                # Build proxy URLs exactly as expected by the library
                http_proxy = f"http://{proxy_parts['username']}:{proxy_parts['password']}@{proxy_parts['host']}:{proxy_parts['port']}"
                
                # Configure using both http and https URLs
                proxy_config = GenericProxyConfig(
                    http_url=http_proxy,
                )
                print(f"Using proxy configuration for request: {proxy_parts['host']}:{proxy_parts['port']}")
                print(f"HTTP proxy: {http_proxy.replace(proxy_parts['password'], '****')}")
                sys.stdout.flush()
            else:
                return jsonify({"error": "Invalid proxy string format. Expected format: username:password@hostname:port"}), 400
        
        # Create YouTubeTranscriptApi instance with proxy config
        ytt_api = YouTubeTranscriptApi(proxy_config=proxy_config)
        
        try:
            # Log which endpoint we're about to call
            print(f"Attempting to list transcripts for video: {video_id}")
            sys.stdout.flush()
            
            # Try to get all available transcripts
            transcript_list = ytt_api.list(video_id)
            
            # If we reached here, we have transcripts available
            print(f"Successfully retrieved transcript list")
            sys.stdout.flush()
        except Exception as e:
            print(f"Error connecting to YouTube with proxy: {str(e)}")
            sys.stdout.flush()
            
            # Try a direct fetch as fallback when list fails
            try:
                print(f"Attempting direct fetch as fallback")
                sys.stdout.flush()
                transcript_data = ytt_api.fetch(video_id, languages=[language], preserve_formatting=preserve_formatting)
                return jsonify({
                    "transcript": convert_transcript_to_json(transcript_data), 
                    "language": language,
                    "fallback": True
                })
            except Exception as direct_e:
                print(f"Direct fetch also failed: {str(direct_e)}")
                sys.stdout.flush()
                
            return jsonify({"error": f"Failed to connect to YouTube: {str(e)}. Please check your proxy configuration."}), 500
        
        # Log available languages
        languages = [{"language": t.language_code, "is_generated": t.is_generated} for t in transcript_list]
        print(f"Available languages for {video_id}: {languages}")
        sys.stdout.flush()
        
        # First priority: Try to get manual transcript in requested language (default: English)
        try:
            # Check if manual transcript exists in the requested language
            manual_transcript = transcript_list.find_manually_created_transcript([language])
            if manual_transcript:
                print(f"Found manual transcript in {language}")
                sys.stdout.flush()
                transcript_data = manual_transcript.fetch(preserve_formatting=preserve_formatting)
                return jsonify({
                    "transcript": convert_transcript_to_json(transcript_data), 
                    "language": language,
                    "is_generated": False
                })
        except Exception as e:
            print(f"Error finding manual transcript in {language}: {str(e)}")
            sys.stdout.flush()
            
        # Second priority: Try to get ANY generated transcript in its original language
        try:
            # Get all available language codes to try all possible generated transcripts
            all_languages = [t.language_code for t in transcript_list]
            print(f"Trying to find generated transcript in any language: {all_languages}")
            sys.stdout.flush()
            
            # Try with the specific find_generated_transcript method
            try:
                generated_transcript = transcript_list.find_generated_transcript(all_languages)
                if generated_transcript:
                    original_language = generated_transcript.language_code
                    print(f"Found generated transcript in original language {original_language}")
                    sys.stdout.flush()
                    transcript_data = generated_transcript.fetch(preserve_formatting=preserve_formatting)
                    return jsonify({
                        "transcript": convert_transcript_to_json(transcript_data), 
                        "language": original_language, 
                        "is_generated": True
                    })
            except Exception as gen_e:
                print(f"Error with find_generated_transcript: {str(gen_e)}")
                sys.stdout.flush()
                
            # Alternative approach - try to find ANY generated transcript
            for transcript in transcript_list:
                if transcript.is_generated:
                    print(f"Iterating found generated transcript in {transcript.language_code}")
                    sys.stdout.flush()
                    transcript_data = transcript.fetch(preserve_formatting=preserve_formatting)
                    return jsonify({
                        "transcript": convert_transcript_to_json(transcript_data), 
                        "language": transcript.language_code, 
                        "is_generated": True
                    })
        except Exception as e:
            print(f"Error finding generated transcript: {str(e)}")
            sys.stdout.flush()
            
        # Third priority: Try to get ANY manual transcript and translate it to requested language
        try:
            for transcript in transcript_list:
                if not transcript.is_generated and transcript.is_translatable:
                    print(f"Found manual transcript in {transcript.language_code}, translating to {language}")
                    sys.stdout.flush()
                    translated = transcript.translate(language)
                    transcript_data = translated.fetch(preserve_formatting=preserve_formatting)
                    return jsonify({
                        "transcript": convert_transcript_to_json(transcript_data), 
                        "language": language, 
                        "original_language": transcript.language_code,
                        "translated": True,
                        "is_generated": False
                    })
        except Exception as e:
            print(f"Error translating manual transcript: {str(e)}")
            sys.stdout.flush()
        
        # Fourth priority: Try an auto-generated transcript in ANY language, not just the requested one
        try:
            # Try each transcript individually
            for transcript in transcript_list:
                try:
                    print(f"Trying transcript in {transcript.language_code}, generated: {transcript.is_generated}")
                    transcript_data = transcript.fetch(preserve_formatting=preserve_formatting)
                    return jsonify({
                        "transcript": convert_transcript_to_json(transcript_data), 
                        "language": transcript.language_code,
                        "is_generated": transcript.is_generated
                    })
                except Exception as e:
                    print(f"Error fetching transcript in {transcript.language_code}: {str(e)}")
                    continue
        except Exception as e:
            print(f"Error trying individual transcripts: {str(e)}")
            sys.stdout.flush()
        
        # Last resort: Try a direct fetch with language
        try:
            print(f"Attempting direct fetch with language: {language}")
            sys.stdout.flush()
            transcript_data = ytt_api.fetch(video_id, languages=[language], preserve_formatting=preserve_formatting)
            return jsonify({
                "transcript": convert_transcript_to_json(transcript_data), 
                "language": language
            })
        except Exception as e:
            print(f"Error using fetch method: {str(e)}")
            sys.stdout.flush()
        
        # Try direct fetch with ANY language as final attempt
        try:
            print("Final attempt: direct fetch with any language")
            sys.stdout.flush()
            # Try each language code we know about
            for lang_code in all_languages:
                try:
                    transcript_data = ytt_api.fetch(video_id, languages=[lang_code], preserve_formatting=preserve_formatting)
                    return jsonify({
                        "transcript": convert_transcript_to_json(transcript_data), 
                        "language": lang_code,
                        "last_resort": True
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"Error in final attempt: {str(e)}")
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
