from flask import Flask, request, jsonify, send_from_directory
import os
import shutil
from werkzeug.utils import secure_filename
import uuid
from chatbot import FrameAnalysisBot
from process_frames import ImageProcessor
import config

app = Flask(__name__)

# Initialize the chatbot and image processor
chatbot = FrameAnalysisBot()
image_processor = ImageProcessor()

@app.route('/amg_chatbot/query', methods=['POST'])
def query_chatbot():
    """Handle chatbot queries"""
    data = request.json
    if not data or 'query' not in data:
        return jsonify({'error': 'Query is required'}), 400
    
    query = data['query']
    analysis_type = data.get('analysis_type', 'general')
    
    # Process the query through the chatbot
    response = chatbot.generate_report(query, analysis_type)
    
    return jsonify({'response': response})

@app.route('/amg_chatbot/analyze_frame', methods=['POST'])
def analyze_frame():
    """Analyze a frame from an alert"""
    data = request.json
    if not data or ('frame_id' not in data and 'frame_url' not in data):
        return jsonify({'error': 'Frame ID or URL is required'}), 400
    
    frame_id = data.get('frame_id')
    frame_url = data.get('frame_url')
    
    # If we have a URL, download the image
    if frame_url:
        import requests
        from PIL import Image
        from io import BytesIO
        
        try:
            response = requests.get(frame_url)
            img = Image.open(BytesIO(response.content))
            
            # Save to detected_frames folder
            os.makedirs(config.DETECTED_FOLDER, exist_ok=True)
            img_path = os.path.join(config.DETECTED_FOLDER, f"{frame_id or uuid.uuid4()}.jpg")
            img.save(img_path)
            
            # Process the image
            image_processor.process_image(img_path)
            
            return jsonify({
                'success': True,
                'message': 'Frame analyzed successfully. You can now ask questions about it.'
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid frame data'}), 400

@app.route('/amg_chatbot/upload_frame', methods=['POST'])
def upload_frame():
    """Upload and analyze a new frame"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file:
        # Create directory if it doesn't exist
        os.makedirs(config.DETECTED_FOLDER, exist_ok=True)
        
        # Save the file
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        file_ext = os.path.splitext(filename)[1]
        new_filename = f"{file_id}{file_ext}"
        file_path = os.path.join(config.DETECTED_FOLDER, new_filename)
        file.save(file_path)
        
        # Process the image
        image_processor.process_image(file_path)
        
        return jsonify({
            'success': True,
            'frame_id': file_id,
            'message': 'Frame uploaded and analyzed successfully. You can now ask questions about it.'
        })

@app.route('/amg_chatbot/frames', methods=['GET'])
def get_frames():
    """Get list of analyzed frames"""
    frames = []
    
    # Load the index
    index = image_processor.load_index()
    
    for frame_id, frame_data in index.items():
        frames.append({
            'id': frame_id,
            'caption': frame_data.get('caption', 'No caption available'),
            'path': frame_data.get('path', '')
        })
    
    return jsonify({'frames': frames})

@app.route('/amg_chatbot/frames/<frame_id>', methods=['GET'])
def get_frame(frame_id):
    """Get a specific frame image"""
    # Load the index
    index = image_processor.load_index()
    
    if frame_id in index and 'path' in index[frame_id]:
        frame_path = index[frame_id]['path']
        directory = os.path.dirname(frame_path)
        filename = os.path.basename(frame_path)
        return send_from_directory(directory, filename)
    
    return jsonify({'error': 'Frame not found'}), 404

def integrate_with_main_app(main_app):
    """Register the chatbot routes with the main Flask app"""
    # Register all routes from this blueprint with the main app
    for rule in app.url_map.iter_rules():
        endpoint = app.view_functions[rule.endpoint]
        main_app.add_url_rule(rule.rule, rule.endpoint, endpoint, methods=rule.methods)

if __name__ == '__main__':
    app.run(debug=True, port=5001)