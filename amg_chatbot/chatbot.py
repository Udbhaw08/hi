# chatbot.py
import os
import json
import numpy as np
from pathlib import Path
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer
from PIL import Image
import config
from datetime import datetime

class FrameAnalysisBot:
    def __init__(self):
        self.device = config.DEVICE
        print("Loading embedding model...")
        self.embedder = SentenceTransformer(config.IMAGE_EMBED_MODEL, device=self.device)
        
        print("Loading language model...")
        if config.USE_LLAMA_CPP:
            try:
                from llama_cpp import Llama
                self.llm = Llama(model_path=config.LLAMA_CPP_MODEL_PATH)
                self.use_llama_cpp = True
            except ImportError:
                print("Failed to import llama_cpp. Falling back to transformers.")
                self.use_llama_cpp = False
                self._load_transformers_model()
        else:
            self.use_llama_cpp = False
            self._load_transformers_model()
        
        # Load index
        self.index = self._load_index()
        print(f"Loaded {len(self.index)} frame records")
    
    def _load_transformers_model(self):
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(config.TRANSFORMERS_MODEL)
            self.llm = AutoModelForCausalLM.from_pretrained(config.TRANSFORMERS_MODEL)
            self.llm.to(self.device)
        except Exception as e:
            print(f"Error loading model: {e}")
            print("Falling back to smaller model...")
            self.tokenizer = AutoTokenizer.from_pretrained("facebook/opt-125m")
            self.llm = AutoModelForCausalLM.from_pretrained("facebook/opt-125m")
            self.llm.to(self.device)
    
    def _load_index(self):
        index = []
        if os.path.exists(config.INDEX_PATH):
            with open(config.INDEX_PATH, "r", encoding="utf8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        # Convert embedding back to numpy for vector search
                        if "embedding" in record:
                            record["embedding"] = np.array(record["embedding"])
                        index.append(record)
                    except Exception as e:
                        print(f"Error loading record: {e}")
        return index
    
    def _vector_search(self, query_embedding, top_k=None):
        if top_k is None:
            top_k = config.TOP_K
        
        if not self.index:
            return []
        
        # Calculate cosine similarity
        similarities = []
        for i, record in enumerate(self.index):
            if "embedding" not in record:
                continue
            similarity = np.dot(query_embedding, record["embedding"]) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(record["embedding"])
            )
            similarities.append((i, similarity))
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k results
        results = []
        for i, sim in similarities[:top_k]:
            record = self.index[i].copy()
            record["similarity"] = float(sim)  # Convert to float for JSON serialization
            results.append(record)
        
        return results
    
    def query(self, query_text, analysis_type=None):
        """
        Query the frame database and generate a report
        
        Args:
            query_text: The query text
            analysis_type: Optional type of analysis (people, objects, activities, safety, general)
        
        Returns:
            A report based on the query
        """
        if not self.index:
            return "No frames have been processed yet. Please run process_frames.py first."
        
        # Embed the query
        query_embedding = self.embedder.encode(query_text, convert_to_numpy=True)
        
        # Search for relevant frames
        results = self._vector_search(query_embedding)
        
        if not results:
            return "No relevant frames found."
        
        # Format context for the LLM
        context = self._format_context(results, query_text, analysis_type)
        
        # Generate report
        report = self._generate_report(context)
        
        return report
    
    def _format_context(self, results, query_text, analysis_type=None):
        """Format the context for the LLM"""
        frames_info = []
        
        for i, result in enumerate(results):
            frame_info = f"Frame {i+1}:\n"
            frame_info += f"- Caption: {result.get('caption', 'No caption')}\n"
            frame_info += f"- Timestamp: {datetime.fromtimestamp(result.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')}\n"
            frame_info += f"- Camera: {result.get('camera_id', 'unknown')}\n"
            frame_info += f"- Relevance: {result.get('similarity', 0):.2f}\n"
            frames_info.append(frame_info)
        
        frames_context = "\n".join(frames_info)
        
        if analysis_type and analysis_type in config.ANALYSIS_TYPES:
            analysis_focus = f"Focus your analysis on {analysis_type} in the frames."
        else:
            analysis_focus = "Provide a general analysis of the frames."
        
        prompt = f"""
Based on the following frames detected by a surveillance system, please answer this query: "{query_text}"

{frames_context}

{analysis_focus}

Generate a detailed report that addresses the query specifically. Include relevant details from the frames.
Report:
"""
        return prompt
    
    def _generate_report(self, prompt):
        """Generate a report using the LLM"""
        try:
            if self.use_llama_cpp:
                output = self.llm(prompt, max_tokens=512)
                return output["choices"][0]["text"].strip()
            else:
                inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
                with torch.no_grad():
                    output = self.llm.generate(
                        **inputs, 
                        max_length=len(inputs["input_ids"][0]) + 512,
                        temperature=0.7,
                        do_sample=True
                    )
                response = self.tokenizer.decode(output[0], skip_special_tokens=True)
                # Extract just the generated part (after the prompt)
                return response[len(self.tokenizer.decode(inputs["input_ids"][0], skip_special_tokens=True)):].strip()
        except Exception as e:
            return f"Error generating report: {e}"

def main():
    bot = FrameAnalysisBot()
    
    print("\nWelcome to Frame Analysis Bot!")
    print("Type 'exit' to quit.")
    print("Available analysis types:", ", ".join(config.ANALYSIS_TYPES))
    
    while True:
        query = input("\nEnter your query: ")
        if query.lower() == 'exit':
            break
        
        analysis_type = None
        if query.startswith("/"):
            parts = query[1:].split(" ", 1)
            if len(parts) == 2 and parts[0] in config.ANALYSIS_TYPES:
                analysis_type = parts[0]
                query = parts[1]
        
        print("\nAnalyzing frames...")
        report = bot.query(query, analysis_type)
        print("\n--- REPORT ---")
        print(report)
        print("-------------")

if __name__ == "__main__":
    main()