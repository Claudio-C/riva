from flask import Flask, render_template, request, jsonify, Response, stream_with_context, redirect, url_for
import os
import tempfile
import uuid
import threading
import json
import time
import ssl
import queue
from riva_client import RivaClient

app = Flask(__name__, static_folder='static', template_folder='templates')

# SSL certificate paths - add alternative paths as fallbacks
SSL_CERT_PATHS = [
    "/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem",
    "/etc/ssl/certs/avatar.ligagc.com/fullchain.pem",
    "/home/ia/certs/fullchain.pem"
]

SSL_KEY_PATHS = [
    "/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem",
    "/etc/ssl/private/avatar.ligagc.com/privkey.pem",
    "/home/ia/certs/privkey.pem"
]

# Find the first valid certificate path
SSL_CERT_FILE = next((path for path in SSL_CERT_PATHS if os.path.exists(path)), SSL_CERT_PATHS[0])
SSL_KEY_FILE = next((path for path in SSL_KEY_PATHS if os.path.exists(path)), SSL_KEY_PATHS[0])

# Riva client configuration
RIVA_SERVER = "localhost:50051"  # Default Riva server address
riva_client = RivaClient(RIVA_SERVER)

# Store active streaming sessions
active_sessions = {}

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Transcribe uploaded audio file."""
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file uploaded'}), 400
    
    audio_file = request.files['audio']
    
    # Save the uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
        tmp_filename = tmp_file.name
        audio_file.save(tmp_filename)
    
    try:
        # Process audio file in chunks to simulate streaming
        def audio_chunks():
            chunk_size = 4096  # 4KB chunks
            with open(tmp_filename, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        
        # Get sample rate from request or use default
        sample_rate = int(request.form.get('sample_rate', 16000))
        
        # Get transcription
        results = []
        final_text = ""
        
        for result in riva_client.transcribe_stream(
            audio_chunks(), 
            sample_rate_hz=sample_rate
        ):
            if result['is_final']:
                final_text = result['transcript']
                results.append(final_text)
        
        return jsonify({'transcription': ' '.join(results) if results else final_text})
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_filename):
            os.unlink(tmp_filename)

@app.route('/stream_start', methods=['POST'])
def stream_start():
    """Initialize a streaming session."""
    session_id = str(uuid.uuid4())
    
    # Get sample rate from request or use default
    sample_rate = int(request.args.get('sample_rate', 16000))
    
    # Create queues for audio data and results
    audio_queue = queue.Queue()
    results_queue = queue.Queue()
    
    # Store session info
    active_sessions[session_id] = {
        'created_at': time.time(),
        'audio_queue': audio_queue,
        'results_queue': results_queue,
        'results': [],
        'complete': False,
        'sample_rate': sample_rate
    }
    
    # Start a dedicated thread for this streaming session
    def session_thread():
        try:
            riva_client.create_streaming_session(
                audio_queue=audio_queue,
                results_queue=results_queue,
                sample_rate_hz=sample_rate
            )
        except Exception as e:
            print(f"Error in session thread {session_id}: {e}")
        finally:
            # Mark session as complete when the thread ends
            if session_id in active_sessions:
                active_sessions[session_id]['complete'] = True
    
    # Start the session thread
    thread = threading.Thread(target=session_thread)
    thread.daemon = True
    thread.start()
    
    # Store thread in session
    active_sessions[session_id]['thread'] = thread
    
    return jsonify({'session_id': session_id})

@app.route('/stream_audio/<session_id>', methods=['POST'])
def stream_audio(session_id):
    """Add audio chunk to an existing streaming session."""
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session = active_sessions[session_id]
    
    # Check for data - handle empty requests as result polling
    is_polling = not request.data or len(request.data) == 0
    
    # Only add audio to queue if there's actual data
    if not is_polling:
        try:
            session['audio_queue'].put(request.data)
        except Exception as e:
            print(f"Error queuing audio chunk: {e}")
            return jsonify({'error': f'Failed to process audio: {str(e)}'}), 500
    
    # Collect any new results
    try:
        while not session['results_queue'].empty():
            result = session['results_queue'].get_nowait()
            session['results'].append(result)
            session['results_queue'].task_done()
    except Exception as e:
        print(f"Error collecting results: {e}")
    
    # Return the latest results
    latest_results = [r['transcript'] for r in session['results'] if r.get('is_final', False)]
    
    # If no final results, get latest interim result
    if not latest_results and session['results']:
        latest_results = [session['results'][-1]['transcript']]
    
    return jsonify({
        'transcription': ' '.join(latest_results) if latest_results else '',
        'is_final': any(r.get('is_final', False) for r in session['results']) if session['results'] else False,
        'num_results': len(session['results'])
    })

@app.route('/stream_stop/<session_id>', methods=['POST'])
def stream_stop(session_id):
    """Finalize a streaming session and get the complete transcription."""
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session ID'}), 400
    
    session = active_sessions[session_id]
    
    # Signal the streaming thread to stop by putting None in the queue
    try:
        session['audio_queue'].put(None)
        
        # Wait for any final results (with timeout)
        end_time = time.time() + 2.0  # 2 second timeout
        while time.time() < end_time:
            try:
                if not session['results_queue'].empty():
                    result = session['results_queue'].get_nowait()
                    session['results'].append(result)
                    session['results_queue'].task_done()
                else:
                    # No more results, break out
                    break
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error collecting final results: {e}")
                break
        
        # Mark session as complete
        session['complete'] = True
    except Exception as e:
        print(f"Error stopping session {session_id}: {e}")
    
    # Get final transcription
    final_results = [r['transcript'] for r in session['results'] if r.get('is_final', False)]
    final_transcription = ' '.join(final_results) if final_results else ''
    
    # Cleanup session after a delay
    def cleanup_session():
        time.sleep(60)  # Keep session for 1 minute
        if session_id in active_sessions:
            del active_sessions[session_id]
    
    threading.Thread(target=cleanup_session).start()
    
    return jsonify({'final_transcription': final_transcription})

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint."""
    cert_exists = os.path.exists(SSL_CERT_FILE)
    key_exists = os.path.exists(SSL_KEY_FILE)
    
    return jsonify({
        'status': 'healthy', 
        'server': 'Riva Flask API',
        'ssl': {
            'cert_path': SSL_CERT_FILE,
            'cert_exists': cert_exists,
            'key_path': SSL_KEY_FILE,
            'key_exists': key_exists
        }
    })

@app.route('/ssl-check')
def ssl_check():
    """Endpoint to check SSL configuration."""
    cert_exists = os.path.exists(SSL_CERT_FILE)
    key_exists = os.path.exists(SSL_KEY_FILE)
    
    return jsonify({
        'ssl_configured': cert_exists and key_exists,
        'cert_file': SSL_CERT_FILE,
        'cert_exists': cert_exists,
        'key_file': SSL_KEY_FILE,
        'key_exists': key_exists,
        'checked_cert_paths': SSL_CERT_PATHS,
        'checked_key_paths': SSL_KEY_PATHS
    })

def check_ssl_config():
    """Check if SSL certificates exist and are valid."""
    if not os.path.exists(SSL_CERT_FILE):
        print(f"Warning: SSL certificate not found at {SSL_CERT_FILE}")
        print(f"Checked paths: {SSL_CERT_PATHS}")
        print("Running without SSL (not secure).")
        return False
    
    if not os.path.exists(SSL_KEY_FILE):
        print(f"Warning: SSL key not found at {SSL_KEY_FILE}")
        print(f"Checked paths: {SSL_KEY_PATHS}")
        print("Running without SSL (not secure).")
        return False
    
    try:
        # Try to create an SSL context with the certificates
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=SSL_CERT_FILE, keyfile=SSL_KEY_FILE)
        
        # Print certificate details for debugging
        with open(SSL_CERT_FILE, 'r') as f:
            cert_content = f.read()
            print(f"Certificate details: {cert_content[:100]}...")
        
        print(f"SSL certificates loaded successfully from:")
        print(f"  - Certificate: {SSL_CERT_FILE}")
        print(f"  - Private key: {SSL_KEY_FILE}")
        return context
    except Exception as e:
        print(f"Error loading SSL certificates: {e}")
        print("Running without SSL (not secure).")
        return False

if __name__ == '__main__':
    # Create a proper SSL context if certificates exist
    ssl_context = check_ssl_config()
    
    if ssl_context:
        # Run with SSL
        print("Starting Flask app with SSL on port 5000")
        app.run(host='0.0.0.0', port=5000, ssl_context=ssl_context)
    else:
        # Run without SSL
        print("Starting Flask app WITHOUT SSL on port 5000")
        app.run(host='0.0.0.0', port=5000)
