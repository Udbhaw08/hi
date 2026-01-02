import { useState } from 'react';
import { uploadVideo } from '../api';

export default function VideoUpload({ admin }){
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const handleUpload = async () => {
    if(!file || !admin) return;
    const fd = new FormData();
    fd.append('username', admin.username);
    fd.append('password', admin.password);
    fd.append('file', file);
    const res = await uploadVideo(fd);
    setResult(res.data);
  };
  return (
    <div>
      <h3>Video Upload</h3>
      <input type='file' accept='video/*' onChange={e=>setFile(e.target.files[0])} />
      <button onClick={handleUpload}>Process</button>
      {result && <pre style={{maxWidth:'400px', whiteSpace:'pre-wrap'}}>{JSON.stringify(result,null,2)}</pre>}
    </div>
  );
}