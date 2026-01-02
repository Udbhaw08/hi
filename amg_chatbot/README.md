# AMG Frame Analysis Chatbot

This chatbot analyzes detected frames from surveillance footage and generates reports based on user queries.

## Setup

1. Install dependencies:
```
pip install -r requirements.txt
```

2. Make sure your detected frames are in the `detected_frames` folder (JPG, PNG formats supported)

## Usage

### Step 1: Process Frames
First, process all frames to generate embeddings and captions:

```
python process_frames.py
```

This will:
- Scan the `detected_frames` folder for images
- Generate captions for each image
- Create embeddings for semantic search
- Save all data to `index.jsonl`

### Step 2: Query the Chatbot
Run the chatbot interface:

```
python chatbot.py
```

You can ask questions like:
- "Show me all frames with people wearing red shirts"
- "Were there any suspicious activities yesterday?"
- "How many vehicles were detected in the parking area?"

### Analysis Types
You can focus your query on specific types of analysis by using the format:
`/analysis_type your query`

Available analysis types:
- `/people` - Focus on people detection and analysis
- `/objects` - Focus on object detection
- `/activities` - Focus on activities and behaviors
- `/safety` - Focus on safety concerns
- `/general` - General analysis (default)

Example: `/people How many people were wearing hats?`

## Configuration

Edit `config.py` to customize:
- Model selection
- Device settings (CPU/GPU)
- Analysis types
- Frame storage locations