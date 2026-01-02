import { useState, useRef } from "react";
import { addPerson } from "../api";

export default function AddPerson({ admin, onAdded }) {
  const [name, setName] = useState("");
  const [personId, setPersonId] = useState("");
  const [flag, setFlag] = useState("whitelist");
  const [metadata, setMetadata] = useState("");
  const [file, setFile] = useState(null);
  const [useCamera, setUseCamera] = useState(false);
  const [preview, setPreview] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [submitting, setSubmitting] = useState(false);

  const startCamera = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = s;
      if (videoRef.current) {
        videoRef.current.srcObject = s;
        videoRef.current.play();
      }
      setUseCamera(true);
    } catch (e) {
      alert("Camera access denied");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setUseCamera(false);
  };

  const capture = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0);
    canvas.toBlob(b => {
      if (b) {
        const f = new File([b], `${personId || 'capture'}.jpg`, { type: 'image/jpeg' });
        setFile(f);
        setPreview(URL.createObjectURL(f));
      }
    }, 'image/jpeg', 0.9);
  };

  const resetForm = () => {
    setName("");
    setPersonId("");
    setFlag("whitelist");
    setMetadata("");
    setFile(null);
    setPreview(null);
    if (useCamera) stopCamera();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!admin) {
      alert("Not logged in");
      return;
    }
    if (!file) {
      alert("Provide image (upload or capture)");
      return;
    }
    setSubmitting(true);
    const formData = new FormData();
    formData.append("username", admin.username);
    formData.append("password", admin.password);
    formData.append("name", name);
    formData.append("person_id", personId);
    formData.append("flag", flag);
    formData.append("metadata", metadata);
    formData.append("file", file);
    try {
      const res = await addPerson(formData);
      alert("Person added: " + res.data.person_id);
      if (onAdded) onAdded();
      resetForm();
    } catch (e) {
      let msg = 'Failed to add person';
      if(e.response && e.response.data && e.response.data.detail){
        if(typeof e.response.data.detail === 'object'){
          msg += `: ${e.response.data.detail.error || ''} ${e.response.data.detail.model_last_error || ''}`;
        } else {
          msg += `: ${e.response.data.detail}`;
        }
      }
      alert(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <h2>Add Person</h2>
      <form onSubmit={handleSubmit} className="form-grid">
        <label>
          <span>Name</span>
          <input required value={name} onChange={e => setName(e.target.value)} />
        </label>
        <label>
          <span>Person ID</span>
            <input required value={personId} onChange={e => setPersonId(e.target.value)} />
        </label>
        <label>
          <span>Flag</span>
          <select value={flag} onChange={e => setFlag(e.target.value)}>
            <option value="whitelist">Whitelist</option>
            <option value="blacklist">Blacklist</option>
          </select>
        </label>
        <label className="full-row">
          <span>Metadata (notes)</span>
          <textarea rows={3} value={metadata} onChange={e => setMetadata(e.target.value)} placeholder="Optional notes / role / remarks" />
        </label>
        <label className="full-row">
          <span>Upload Image</span>
          <input type="file" accept="image/*" onChange={e => { setFile(e.target.files[0]); setPreview(URL.createObjectURL(e.target.files[0])); }} />
        </label>
        <div className="full-row camera-block">
          {!useCamera && <button type="button" onClick={startCamera}>Use Camera</button>}
          {useCamera && (
            <div className="cam-wrapper">
              <video ref={videoRef} className="cam-video" />
              <div className="btn-row">
                <button type="button" onClick={capture}>Capture</button>
                <button type="button" onClick={stopCamera}>Stop</button>
              </div>
            </div>
          )}
          {preview && <img className="preview" src={preview} alt="preview" />}
        </div>
        <div className="full-row btn-row">
          <button type="submit" disabled={submitting}>{submitting ? "Saving..." : "Submit"}</button>
          <button type="button" onClick={resetForm} disabled={submitting}>Reset</button>
        </div>
      </form>
    </div>
  );
}
