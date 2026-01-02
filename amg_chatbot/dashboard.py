import os
import json
import numpy as np
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import config
from chatbot import FrameAnalysisBot
from PIL import Image
import base64
from io import BytesIO
import time

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = config.DETECTED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Initialize the chatbot
bot = FrameAnalysisBot()

# Ensure the upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Create templates directory if it doesn't exist
os.makedirs(os.path.join(os.path.dirname(__file__), 'templates'), exist_ok=True)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/query', methods=['POST'])
def query():
    data = request.json
    query_text = data.get('query', '')
    analysis_type = data.get('analysis_type')
    
    if not query_text:
        return jsonify({'error': 'No query provided'}), 400
    
    result = bot.query(query_text, analysis_type)
    return jsonify({'result': result})

@app.route('/api/frames', methods=['GET'])
def get_frames():
    frames = []
    if os.path.exists(config.INDEX_PATH):
        with open(config.INDEX_PATH, 'r', encoding='utf8') as f:
            for line in f:
                try:
                    record = json.loads(line)
                    # Don't include the embedding in the response
                    if 'embedding' in record:
                        del record['embedding']
                    frames.append(record)
                except Exception as e:
                    print(f"Error loading record: {e}")
    
    return jsonify({'frames': frames})

@app.route('/api/analyze_frame', methods=['POST'])
def analyze_frame():
    # Check if a file was uploaded
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Process the uploaded frame
        try:
            # Load the image
            img = Image.open(filepath).convert("RGB")
            
            # Get caption from the bot
            processor = bot.caption_processor
            model = bot.caption_model
            
            inputs = processor(images=img, return_tensors="pt").to(bot.device)
            out = model.generate(**inputs, max_length=40)
            caption = processor.decode(out[0], skip_special_tokens=True)
            
            # Get embedding
            embedding = bot.embedder.encode(caption, convert_to_numpy=True).tolist()
            
            # Create record
            record = {
                "frame_id": f"frame_{int(time.time()*1000)}",
                "file_path": filepath,
                "timestamp": int(os.path.getmtime(filepath)),
                "camera_id": "manual_upload",
                "caption": caption,
                "embedding": embedding,
                "notes": "manually uploaded"
            }
            
            # Save to index
            with open(config.INDEX_PATH, "a", encoding='utf8') as f:
                f.write(json.dumps(record) + "\n")
            
            # Convert image to base64 for display
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Return analysis results
            return jsonify({
                'success': True,
                'caption': caption,
                'image': f"data:image/jpeg;base64,{img_str}"
            })
            
        except Exception as e:
            return jsonify({'error': f'Error processing image: {str(e)}'}), 500
    
    return jsonify({'error': 'Unknown error'}), 500

@app.route('/frames/<path:filename>')
def serve_frame(filename):
    return send_from_directory(config.DETECTED_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)