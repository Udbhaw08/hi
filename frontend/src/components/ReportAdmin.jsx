import React, { useState, useRef, useEffect } from 'react';
import { saveDetection, getAllDetections, deleteDetection } from '../api/detectionApi';
import '../styles/ReportAdmin.css';

const ReportAdmin = () => {
  const [uploadedImage, setUploadedImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [alert, setAlert] = useState(null);
  const [recentReports, setRecentReports] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const fileInputRef = useRef(null);

  const [formData, setFormData] = useState({
    timestamp: '',
    age: '',
    gender: '',
    height: '',
    build: '',
    clothes: '',
    location: '',
    description: '',
  });

  useEffect(() => {
    // Set current date/time as default
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    setFormData(prev => ({ ...prev, timestamp: now.toISOString().slice(0, 16) }));
  }, []);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleImageUpload = (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setUploadedImage(event.target.result);
        setPreviewUrl(event.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const showAlertMessage = (message, type) => {
    setAlert({ message, type });
    setTimeout(() => setAlert(null), 5000);
  };

  const loadHistory = async () => {
    try {
      const result = await getAllDetections();
      if (result.success) {
        setRecentReports(result.data);
        setShowHistory(true);
      }
    } catch (error) {
      showAlertMessage('Failed to load history', 'error');
    }
  };

  const handleDelete = async (id) => {
    try {
      const result = await deleteDetection(id);
      if (result.success) {
        setRecentReports(prev => prev.filter(r => r._id !== id));
        showAlertMessage('Record deleted successfully', 'success');
      }
    } catch (error) {
      showAlertMessage('Failed to delete record', 'error');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!uploadedImage) {
      showAlertMessage('⚠️ Please upload a photo before submitting!', 'error');
      return;
    }

    const detectionData = {
      camera: 'CAMERA 01',
      image: uploadedImage,
      timestamp: new Date(formData.timestamp),
      age: formData.age,
      gender: formData.gender,
      height: formData.height,
      build: formData.build,
      clothes: formData.clothes,
      location: formData.location,
      description: formData.description,
    };

    setLoading(true);

    try {
      const result = await saveDetection(detectionData);

      if (result.success) {
        showAlertMessage('✅ Detection record saved successfully! NFC tap will now show this data.', 'success');

        // Reset form
        setTimeout(() => {
          setFormData({
            timestamp: new Date().toISOString().slice(0, 16),
            age: '',
            gender: '',
            height: '',
            build: '',
            clothes: '',
            location: '',
            description: '',
          });
          setUploadedImage(null);
          setPreviewUrl(null);
          if (fileInputRef.current) fileInputRef.current.value = '';
        }, 2000);
      } else {
        showAlertMessage('❌ Error: ' + result.message, 'error');
      }
    } catch (error) {
      showAlertMessage('❌ Failed to connect to detection server. Make sure the detection-system backend is running on port 5000!', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="report-page">
      <div className="report-container">
        {/* Header */}
        <div className="report-header">
          <div className="report-header-left">
            <h1>🔐 Detection Report</h1>
            <p>DRISHTI - Data Entry for NFC Detection System</p>
          </div>
          <div className="report-camera-badge">📹 CAMERA</div>
        </div>

        {/* Alert */}
        {alert && (
          <div className={`report-alert report-alert-${alert.type}`}>
            {alert.message}
          </div>
        )}

        {/* Content */}
        <div className="report-content">
          {/* Photo Section */}
          <div className="report-photo-section">
            <div className="report-section-title">📸 PERSON IMAGE</div>
            <div
              className="report-upload-area"
              onClick={() => fileInputRef.current?.click()}
            >
              {previewUrl ? (
                <img src={previewUrl} alt="Preview" className="report-preview-img" />
              ) : (
                <div className="report-upload-placeholder">
                  <div className="report-upload-icon">🖼️</div>
                  <div className="report-upload-text">Click to Upload Photo</div>
                  <div className="report-upload-hint">Supported: JPG, PNG, JPEG</div>
                </div>
              )}
              <input
                type="file"
                ref={fileInputRef}
                accept="image/*"
                onChange={handleImageUpload}
                style={{ display: 'none' }}
              />
            </div>
          </div>

          {/* Details Section */}
          <div className="report-details-section">
            <div className="report-section-title">📋 PERSON DETAILS</div>

            {loading && (
              <div className="report-loading">⏳ Saving to database...</div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="report-info-box">
                <div className="report-form-group">
                  <label>Date & Time</label>
                  <input
                    type="datetime-local"
                    name="timestamp"
                    value={formData.timestamp}
                    onChange={handleInputChange}
                    required
                  />
                </div>
              </div>

              <div className="report-row">
                <div className="report-form-group">
                  <label>Approximate Age</label>
                  <input
                    type="number"
                    name="age"
                    value={formData.age}
                    onChange={handleInputChange}
                    placeholder="e.g., 25"
                    min="0"
                    max="150"
                  />
                </div>
                <div className="report-form-group">
                  <label>Gender</label>
                  <select name="gender" value={formData.gender} onChange={handleInputChange}>
                    <option value="">Select Gender</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="unknown">Unknown</option>
                  </select>
                </div>
              </div>

              <div className="report-row">
                <div className="report-form-group">
                  <label>Height (approx.)</label>
                  <input
                    type="text"
                    name="height"
                    value={formData.height}
                    onChange={handleInputChange}
                    placeholder="e.g., 5'8&quot; / 173cm"
                  />
                </div>
                <div className="report-form-group">
                  <label>Build</label>
                  <select name="build" value={formData.build} onChange={handleInputChange}>
                    <option value="">Select Build</option>
                    <option value="slim">Slim</option>
                    <option value="average">Average</option>
                    <option value="heavy">Heavy</option>
                  </select>
                </div>
              </div>

              <div className="report-form-group">
                <label>Clothing Description</label>
                <input
                  type="text"
                  name="clothes"
                  value={formData.clothes}
                  onChange={handleInputChange}
                  placeholder="e.g., Blue jeans, white t-shirt, black cap"
                />
              </div>

              <div className="report-form-group">
                <label>Specific Location</label>
                <input
                  type="text"
                  name="location"
                  value={formData.location}
                  onChange={handleInputChange}
                  placeholder="e.g., Main entrance, Building A"
                />
              </div>

              <div className="report-form-group">
                <label>Additional Remarks</label>
                <textarea
                  name="description"
                  value={formData.description}
                  onChange={handleInputChange}
                  placeholder="Any distinguishing features, behavior, or other relevant information..."
                />
              </div>

              <button type="submit" className="report-submit-btn" disabled={loading}>
                {loading ? '⏳ Saving...' : '💾 SAVE TO DATABASE'}
              </button>
            </form>

            <div className="report-nfc-info">
              <strong>📱 NFC Integration:</strong> Once saved, this detection record becomes the latest entry. 
              When someone taps the NFC tag, they will see this data on the display page served by the detection-system backend.
            </div>
          </div>
        </div>

        {/* History Toggle */}
        <div className="report-history-section">
          <button className="report-history-btn" onClick={loadHistory}>
            📜 {showHistory ? 'Refresh' : 'View'} Detection History
          </button>

          {showHistory && recentReports.length > 0 && (
            <div className="report-history-list">
              {recentReports.map((report) => (
                <div key={report._id} className="report-history-item">
                  <div className="report-history-img-wrapper">
                    <img src={report.image} alt="Detection" className="report-history-img" />
                  </div>
                  <div className="report-history-details">
                    <div className="report-history-meta">
                      <span className="report-history-camera">{report.camera}</span>
                      <span className="report-history-time">
                        {new Date(report.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="report-history-info">
                      {report.age && <span>Age: {report.age}</span>}
                      {report.gender && <span> • {report.gender}</span>}
                      {report.location && <span> • 📍 {report.location}</span>}
                    </div>
                    {report.clothes && (
                      <div className="report-history-clothes">👕 {report.clothes}</div>
                    )}
                  </div>
                  <button
                    className="report-history-delete"
                    onClick={() => handleDelete(report._id)}
                    title="Delete record"
                  >
                    🗑️
                  </button>
                </div>
              ))}
            </div>
          )}

          {showHistory && recentReports.length === 0 && (
            <p style={{ textAlign: 'center', color: '#6b7280', padding: '2rem' }}>
              No detection records found.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReportAdmin;
