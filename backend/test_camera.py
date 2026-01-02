import cv2
import time

def test_camera(camera_index=0):
    print(f"Attempting to access camera at index {camera_index}...")
    cap = cv2.VideoCapture(camera_index)
    
    if not cap.isOpened():
        print(f"ERROR: Could not open camera at index {camera_index}")
        return False
    
    print(f"SUCCESS: Camera at index {camera_index} opened successfully")
    print("Attempting to read a frame...")
    
    ret, frame = cap.read()
    if not ret:
        print("ERROR: Could not read frame from camera")
        cap.release()
        return False
    
    print(f"SUCCESS: Read frame with shape {frame.shape}")
    print("Camera is working properly!")
    
    # Release the camera
    cap.release()
    return True

if __name__ == "__main__":
    # Test default camera (index 0)
    if not test_camera(0):
        print("\nTrying alternative camera index...")
        # Try alternative camera index
        test_camera(1)