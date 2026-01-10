import React, { useState } from 'react';
import axios from 'axios';

const Teacher: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);

  const handleFileUpload = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    try {
      await axios.post('http://localhost:8000/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      alert('File uploaded successfully!');
    } catch (err) {
      console.error("Upload failed", err);
      alert('Upload failed');
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl mb-4">Upload Lesson</h2>

          <div className="form-control w-full">
            <label className="label">
              <span className="label-text">Pick a file to upload</span>
            </label>
            <input
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="file-input file-input-bordered w-full"
            />
          </div>

          <div className="card-actions justify-end mt-4">
            <button
              onClick={handleFileUpload}
              disabled={!file}
              className="btn btn-primary"
            >
              Upload to Backboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Teacher;
