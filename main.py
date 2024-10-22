import os
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from google.cloud import speech, texttospeech, language_v1
from google.oauth2 import service_account
import io
import json
import logging
from flask_cors import CORS
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)

# Set up credentials
credentials = service_account.Credentials.from_service_account_file(
    "voiceinteractionapp-436602-64413c96f909.json",
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

# Initialize clients
speech_client = speech.SpeechClient(credentials=credentials)
tts_client = texttospeech.TextToSpeechClient(credentials=credentials)
language_client = language_v1.LanguageServiceClient(credentials=credentials)

def analyze_sentiment(text):
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    try:
        sentiment = language_client.analyze_sentiment(request={'document': document}).document_sentiment
        return {
            'category': 'positive' if sentiment.score > 0.25 else 'negative' if sentiment.score < -0.25 else 'neutral',
            'score': sentiment.score,
            'magnitude': sentiment.magnitude
        }
    except Exception as e:
        app.logger.error(f"Sentiment analysis error: {str(e)}")
        return None

def save_file(content, file_type, text_content=None, sentiment=None):
    filename = f"{file_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    audio_filepath = os.path.join(os.getcwd(), 'saved_files', f"{filename}.mp3")
    text_filepath = os.path.join(os.getcwd(), 'saved_files', f"{filename}.txt")
    os.makedirs(os.path.dirname(audio_filepath), exist_ok=True)
    
    try:
        if file_type == 'speech':
            with open(audio_filepath, 'wb') as f:
                f.write(content)
            with open(text_filepath, 'w', encoding='utf-8') as f:
                f.write(text_content)
                if sentiment:
                    f.write(f"\n\nSentiment Analysis:\n")
                    f.write(f"Category: {sentiment['category']}\n")
                    f.write(f"Score: {sentiment['score']}\n")
                    f.write(f"Magnitude: {sentiment['magnitude']}\n")
        else:
            with open(text_filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                if sentiment:
                    f.write(f"\n\nSentiment Analysis:\n")
                    f.write(f"Category: {sentiment['category']}\n")
                    f.write(f"Score: {sentiment['score']}\n")
                    f.write(f"Magnitude: {sentiment['magnitude']}\n")
        return filename  # Return just the filename for easier linking
    except Exception as e:
        app.logger.error(f"Error saving {file_type}: {str(e)}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/transcribe', methods=['POST'])
def transcribe():
    app.logger.info("Transcribe endpoint hit")
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400

    audio_file = request.files['audio']
    audio_content = audio_file.read()

    if not audio_content:
        return jsonify({'error': 'Empty audio content'}), 400

    audio = speech.RecognitionAudio(content=audio_content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
        sample_rate_hertz=48000,
        language_code="en-US",
    )

    try:
        response = speech_client.recognize(config=config, audio=audio)
        transcription = ' '.join([result.alternatives[0].transcript for result in response.results])
        sentiment_result = analyze_sentiment(transcription)
        saved_filename = save_file(transcription, 'transcription', sentiment=sentiment_result)

        return jsonify({
            'transcription': transcription,
            'sentiment': sentiment_result,
            'saved_filename': saved_filename  # Return just the filename for easier linking
        })
    except Exception as e:
        app.logger.error(f"Transcription error: {str(e)}")
        return jsonify({'error': f'Transcription failed: {str(e)}'}), 500

@app.route('/generate-speech', methods=['POST'])
def generate_speech():
    app.logger.info("Generate speech endpoint hit")
    text = request.json.get('text')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    sentiment_result = analyze_sentiment(text)
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    try:
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        saved_filename = save_file(response.audio_content, 'speech', text_content=text, sentiment=sentiment_result)

        return send_file(
            io.BytesIO(response.audio_content),
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name='speech.mp3'
        ), 200, {
            'X-Sentiment': json.dumps(sentiment_result),
            'X-File-Name': saved_filename  # Return just the filename for easier linking
        }
    except Exception as e:
        app.logger.error(f"Speech generation error: {str(e)}")
        return jsonify({'error': f'Speech generation failed: {str(e)}'}), 500

@app.route('/saved_files/<path:filename>')
def serve_file(filename):
    return send_from_directory('saved_files', filename)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))