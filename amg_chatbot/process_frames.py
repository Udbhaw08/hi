# process_frames.py
import os, json, time
from pathlib import Path
import numpy as np
from PIL import Image
from tqdm import tqdm
import torch
from sentence_transformers import SentenceTransformer
from transformers import BlipProcessor, BlipForConditionalGeneration
import config

class ImageProcessor:
    def __init__(self):
        self.device = config.DEVICE
        self.load_models()
        os.makedirs(config.DETECTED_FOLDER, exist_ok=True)
        os.makedirs(os.path.dirname(config.INDEX_PATH), exist_ok=True)
        
    def load_models(self):
        print("Loading caption model...")
        self.caption_processor = BlipProcessor.from_pretrained(config.CAPTION_MODEL)
        self.caption_model = BlipForConditionalGeneration.from_pretrained(config.CAPTION_MODEL).to(self.device)
        
        print("Loading image/text embedding model...")
        self.embedder = SentenceTransformer(config.IMAGE_EMBED_MODEL, device=self.device)
    
    def generate_caption(self, image):
        """Generate a caption for an image"""
        image = image.convert("RGB")
        inputs = self.caption_processor(images=image, return_tensors="pt").to(self.device)
        out = self.caption_model.generate(**inputs, max_length=40)
        caption = self.caption_processor.decode(out[0], skip_special_tokens=True)
        return caption
    
    def generate_embedding(self, image=None, text=None):
        """Generate embedding from image or text"""
        if text:
            return self.embedder.encode(text, convert_to_numpy=True)
        elif image:
            # First generate caption, then embed the caption text
            caption = self.generate_caption(image)
            return self.embedder.encode(caption, convert_to_numpy=True)
        else:
            raise ValueError("Either image or text must be provided")
    
    def process_image(self, file_path):
        """Process a single image and add it to the index"""
        try:
            img = Image.open(file_path).convert("RGB")
            caption = self.generate_caption(img)
            embedding = self.generate_embedding(text=caption)
            
            record = {
                "frame_id": f"frame_{int(time.time()*1000)}",
                "file_path": file_path,
                "timestamp": file_timestamp(file_path),
                "camera_id": Path(file_path).stem.split("_")[0] if "_" in Path(file_path).stem else "unknown",
                "caption": caption,
                "embedding": embedding.tolist(),
                "notes": "auto-generated"
            }
            
            self.add_to_index(record)
            return record
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return None
    
    def add_to_index(self, record):
        """Add a record to the index file"""
        # Load existing index
        index_data = {}
        if os.path.exists(config.INDEX_PATH):
            try:
                with open(config.INDEX_PATH, 'r') as f:
                    index_data = json.load(f)
            except json.JSONDecodeError:
                # If the file is corrupted or empty, start with an empty dict
                pass
        
        # Add new record
        index_data[record['file_path']] = record
        
        # Save updated index
        with open(config.INDEX_PATH, 'w') as f:
            json.dump(index_data, f)
    
    def process_folder(self):
        """Process all images in the detected folder"""
        # Get list of image files
        files = sorted([str(p) for p in Path(config.DETECTED_FOLDER).glob("*.*") 
                       if p.suffix.lower() in [".jpg", ".png", ".jpeg"]])
        
        # Load existing index to avoid reprocessing
        seen = set()
        if os.path.exists(config.INDEX_PATH):
            try:
                with open(config.INDEX_PATH, 'r') as f:
                    index_data = json.load(f)
                    seen = set(index_data.keys())
            except json.JSONDecodeError:
                pass
        
        # Process new files
        new_count = 0
        for fp in tqdm(files):
            if fp in seen:
                continue
            
            if self.process_image(fp):
                new_count += 1
                seen.add(fp)
        
        print(f"Done. New records: {new_count}")

# Helper functions
def file_timestamp(path):
    return int(os.path.getmtime(path))

def main():
    processor = ImageProcessor()
    processor.process_folder()

if __name__ == "__main__":
    main()
