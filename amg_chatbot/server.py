import os
import time
import json
import uuid
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import torch
from PIL import Image

# Import our modules
from config import DETECTED_FOLDER, INDEX_PATH, TRANSFORMERS_MODEL, ANALYSIS_TYPES
from process_frames import ImageProcessor
from chatbot import FrameAnalysisBot

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = DETECTED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Create folders if they don't exist
os.makedirs(DETECTED_FOLDER, exist_ok=True)
os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)

# Initialize processor and chatbot
image_processor = ImageProcessor()
chatbot = FrameAnalysisBot()

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/frames/<path:filename>')
def serve_frame(filename):
    return send_from_directory(DETECTED_FOLDER, filename)

@app.route('/api/frames')
def get_frames():
    try:
        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, 'r') as f:
                index_data = json.load(f)
                # Sort by timestamp (newest first)
                frames = sorted(index_data.values(), key=lambda x: x.get('timestamp', 0), reverse=True)
                return jsonify({'frames': frames[:50]})  # Return the 50 most recent frames
        return jsonify({'frames': []})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/query', methods=['POST'])
def query_frames():
    try:
        data = request.json
        query = data.get('query', '')
        analysis_type = data.get('analysis_type', '')
        
        if not query:
            return jsonify({'error': 'Query is required'})
        
        # Format query with analysis type if provided
        formatted_query = query
        if analysis_type and analysis_type in ANALYSIS_TYPES:
            formatted_query = f"/{analysis_type} {query}"
        
        # Get response from chatbot
        response = chatbot.generate_report(formatted_query)
        return jsonify({'result': response})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/analyze_frame', methods=['POST'])
def analyze_frame():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'})
        
        # Save the file with a unique name
        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process the image
        caption = image_processor.generate_caption(Image.open(filepath))
        
        # Add to index
        timestamp = time.time()
        frame_data = {
            'file_path': filepath,
            'caption': caption,
            'timestamp': timestamp,
            'embedding': image_processor.generate_embedding(Image.open(filepath)).tolist()
        }
        
        # Update index file
        index_data = {}
        if os.path.exists(INDEX_PATH):
            with open(INDEX_PATH, 'r') as f:
                index_data = json.load(f)
        
        index_data[filepath] = frame_data
        
        with open(INDEX_PATH, 'w') as f:
            json.dump(index_data, f)
        
        return jsonify({
            'caption': caption,
            'file_path': filepath
        })
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)