# NVIDIA Riva Flask Demo

A Flask-based web application that demonstrates the capabilities of NVIDIA Riva ASR (Automatic Speech Recognition) and TTS (Text-to-Speech) services.

## Requirements

- Python 3.8 or higher
- Flask
- NVIDIA Riva client library (version 2.19.0)
- SSL certificates for secure connections

## Installation

1. Install the required Python packages:

```bash
pip install -r requirements.txt
```

2. Make sure NVIDIA Riva server is running on the local machine.

3. Ensure SSL certificates are correctly placed at:
   - Certificate: `/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem`
   - Key: `/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem`

## Running the Application

Start the Flask application:

```bash
python app.py
```

The application will be available at `https://your-machine-ip:5000`

## Features

- Speech-to-Text (ASR) via:
  - Real-time microphone recording
  - Audio file upload
- Text-to-Speech (TTS):
  - Complete text synthesis
  - Streaming synthesis

## Notes

- The application is configured for streaming models as required.
- Default Riva server URL is `localhost:50051`, change in app.py if needed.
