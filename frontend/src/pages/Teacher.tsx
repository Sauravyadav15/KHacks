import React, { useState, useEffect } from 'react';
import axios from 'axios';

interface Category {
  id: number;
  name: string;
  created_at: string;
  is_active: boolean;
}

interface FileItem {
  id: number;
  filename: string;
  original_filename: string;
  file_size: number;
  uploaded_at: string;
  is_active: boolean;
  category_id: number | null;
  category_name: string | null;
}

interface Instruction {
  id: number;
  instruction_name: string;
  instruction_value: string;
  is_active: boolean;
  created_at: string;
}

interface Student {
  username: string;
  full_name: string;
  email: string;
  account_active: number;
}

const Teacher: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [loading, setLoading] = useState(false);

  // Configuration tab state
  const [activeTab, setActiveTab] = useState<'files' | 'config' | 'students'>('files');
  const [instructions, setInstructions] = useState<Instruction[]>([]);
  const [newInstruction, setNewInstruction] = useState({ name: '', value: '' });

  // Students tab state
  const [students, setStudents] = useState<Student[]>([]);
  const [studentsLoading, setStudentsLoading] = useState(false);
  const [studentsError, setStudentsError] = useState<string | null>(null);

  useEffect(() => {
    fetchCategories();
    fetchFiles();
  }, []);

  useEffect(() => {
    if (activeTab === 'config') {
      fetchInstructions();
    }
    if (activeTab === 'students') {
      fetchStudents();
    }
  }, [activeTab]);

  const fetchStudents = async () => {
    setStudentsLoading(true);
    setStudentsError(null);
    try {
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      if (!token) {
        setStudentsError('You must be logged in as a teacher to view students');
        return;
      }
      const response = await axios.get('http://localhost:8000/accounts/students', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setStudents(response.data.students);
    } catch (err: any) {
      console.error("Failed to fetch students", err);
      setStudentsError(err.response?.data?.detail || 'Failed to fetch students');
    } finally {
      setStudentsLoading(false);
    }
  };

  const fetchCategories = async () => {
    try {
      const response = await axios.get('http://localhost:8000/teacher/categories');
      setCategories(response.data.categories);
    } catch (err) {
      console.error("Failed to fetch categories", err);
    }
  };

  const fetchFiles = async () => {
    try {
      const response = await axios.get('http://localhost:8000/teacher/files');
      setFiles(response.data.files);
    } catch (err) {
      console.error("Failed to fetch files", err);
    }
  };

  const fetchInstructions = async () => {
    try {
      const response = await axios.get('http://localhost:8000/teacher/config/instructions');
      setInstructions(response.data.instructions);
    } catch (err) {
      console.error("Failed to fetch instructions", err);
    }
  };

  const handleAddInstruction = async () => {
    if (!newInstruction.name.trim() || !newInstruction.value.trim()) {
      alert('Please provide both name and instruction text');
      return;
    }

    try {
      await axios.post('http://localhost:8000/teacher/config/instructions', {
        name: newInstruction.name,
        value: newInstruction.value
      });
      setNewInstruction({ name: '', value: '' });
      await fetchInstructions();
    } catch (err: any) {
      console.error("Failed to add instruction", err);
      alert(`Failed to add instruction: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleToggleInstruction = async (instructionId: number) => {
    try {
      await axios.post(`http://localhost:8000/teacher/config/instructions/${instructionId}/toggle`);
      await fetchInstructions();
    } catch (err: any) {
      console.error("Failed to toggle instruction", err);
      alert(`Failed to toggle instruction: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDeleteInstruction = async (instructionId: number) => {
    if (!confirm('Are you sure you want to delete this instruction?')) return;

    try {
      await axios.delete(`http://localhost:8000/teacher/config/instructions/${instructionId}`);
      await fetchInstructions();
    } catch (err: any) {
      console.error("Failed to delete instruction", err);
      alert(`Failed to delete instruction: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleFileUpload = async () => {
    if (selectedFiles.length === 0) return;

    const formData = new FormData();
    selectedFiles.forEach((file) => {
      formData.append("files", file);
    });

    try {
      setUploading(true);
      await axios.post('http://localhost:8000/teacher/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setSelectedFiles([]);
      const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      await fetchFiles();
    } catch (err: any) {
      console.error("Upload failed", err);
      const errorMsg = err.response?.data?.detail || err.message || 'Upload failed';
      alert(`Upload failed: ${errorMsg}`);
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelection = (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (fileList) {
      setSelectedFiles(Array.from(fileList));
    }
  };

  const removeSelectedFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) return;

    try {
      await axios.post('http://localhost:8000/teacher/categories', { name: newCategoryName });
      setNewCategoryName('');
      await fetchCategories();
    } catch (err: any) {
      console.error("Failed to create category", err);
      alert(`Failed to create category: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDeleteCategory = async (categoryId: number) => {
    if (!confirm('Are you sure you want to delete this category? Files in this category will become uncategorized.')) return;

    try {
      await axios.delete(`http://localhost:8000/teacher/categories/${categoryId}`);
      await fetchCategories();
      await fetchFiles();
    } catch (err: any) {
      console.error("Failed to delete category", err);
      alert(`Failed to delete category: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleToggleCategoryActive = async (categoryId: number, isActive: boolean) => {
    try {
      const endpoint = isActive ? 'deactivate' : 'activate';
      await axios.post(`http://localhost:8000/teacher/categories/${categoryId}/${endpoint}`);
      await fetchCategories();
    } catch (err: any) {
      console.error("Failed to toggle category active status", err);
      alert(`Failed to update category: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleMoveToCategory = async (fileId: number, categoryId: number | null) => {
    try {
      await axios.put(`http://localhost:8000/teacher/files/${fileId}/category`, {
        category_id: categoryId
      });
      await fetchFiles();
    } catch (err: any) {
      console.error("Failed to move file", err);
      alert(`Failed to move file: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleToggleActive = async (fileId: number, isActive: boolean) => {
    try {
      const endpoint = isActive ? 'deactivate' : 'activate';
      await axios.post(`http://localhost:8000/teacher/files/${fileId}/${endpoint}`);
      await fetchFiles();
    } catch (err: any) {
      console.error("Failed to toggle file active status", err);
      alert(`Failed to update file: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleDeleteFile = async (fileId: number) => {
    if (!confirm('Are you sure you want to delete this file?')) return;

    try {
      await axios.delete(`http://localhost:8000/teacher/files/${fileId}`);
      await fetchFiles();
    } catch (err: any) {
      console.error("Failed to delete file", err);
      alert(`Failed to delete file: ${err.response?.data?.detail || err.message}`);
    }
  };

  const getFilesForCategory = (categoryId: number | null) => {
    return files.filter(f => f.category_id === categoryId);
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Tab Navigation */}
      <div className="tabs tabs-boxed bg-base-100 shadow-xl p-2">
        <a
          className={`tab tab-lg ${activeTab === 'files' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('files')}
        >
          Files & Categories
        </a>
        <a
          className={`tab tab-lg ${activeTab === 'config' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('config')}
        >
          Configuration
        </a>
        <a
          className={`tab tab-lg ${activeTab === 'students' ? 'tab-active' : ''}`}
          onClick={() => setActiveTab('students')}
        >
          Students
        </a>
      </div>

      {/* Files Tab Content */}
      {activeTab === 'files' && (
        <>
          {/* Upload Section */}
          <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl mb-4">Upload Lessons</h2>

          <div className="form-control w-full">
            <label className="label">
              <span className="label-text">Pick one or more files to upload</span>
            </label>
            <input
              type="file"
              multiple={true}
              onChange={handleFileSelection}
              className="file-input file-input-bordered w-full"
              accept="*/*"
            />
          </div>

          {selectedFiles.length > 0 && (
            <div className="mt-4">
              <p className="font-semibold mb-2">Selected files ({selectedFiles.length}):</p>
              <div className="space-y-2">
                {selectedFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between bg-base-200 p-2 rounded">
                    <span className="text-sm">{file.name} ({(file.size / 1024).toFixed(2)} KB)</span>
                    <button
                      onClick={() => removeSelectedFile(index)}
                      className="btn btn-xs btn-circle btn-ghost"
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card-actions justify-end mt-4">
            <button
              onClick={handleFileUpload}
              disabled={selectedFiles.length === 0 || uploading}
              className="btn btn-primary"
            >
              {uploading ? (
                <>
                  <span className="loading loading-spinner"></span>
                  Uploading {selectedFiles.length} file(s)...
                </>
              ) : (
                `Upload ${selectedFiles.length > 0 ? selectedFiles.length + ' file(s)' : 'to Backboard'}`
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Category Management Section */}
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl mb-4">Create Category</h2>

          <div className="flex gap-2">
            <input
              type="text"
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="Category name"
              className="input input-bordered flex-1"
              onKeyDown={(e) => e.key === 'Enter' && handleCreateCategory()}
            />
            <button
              onClick={handleCreateCategory}
              disabled={!newCategoryName.trim()}
              className="btn btn-primary"
            >
              Create
            </button>
          </div>
        </div>
      </div>

      {/* Categories List Section */}
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl mb-4">Manage Categories</h2>

          {categories.length > 0 ? (
            <div className="space-y-2">
              {categories.map((category) => (
                <div key={category.id} className="card bg-base-200 shadow">
                  <div className="card-body p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <p className="font-semibold">{category.name}</p>
                        <p className="text-sm text-gray-500">
                          {getFilesForCategory(category.id).length} file(s)
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleToggleCategoryActive(category.id, category.is_active)}
                          className={`btn btn-sm ${category.is_active ? 'btn-success' : 'btn-outline'}`}
                        >
                          {category.is_active ? 'Active' : 'Inactive'}
                        </button>
                        <button
                          onClick={() => handleDeleteCategory(category.id)}
                          className="btn btn-sm btn-error"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 italic">No categories yet. Create one above!</p>
          )}
        </div>
      </div>

      {/* File Management Section */}
      <div className="card bg-base-100 shadow-xl">
        <div className="card-body">
          <h2 className="card-title text-2xl mb-4">File Management</h2>

          {/* Uncategorized Files */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold mb-2">Uncategorized</h3>
            <div className="space-y-2">
              {getFilesForCategory(null).map((file) => (
                <div key={file.id} className="card bg-base-200 shadow">
                  <div className="card-body p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <p className="font-semibold">{file.original_filename}</p>
                        <p className="text-sm text-gray-500">
                          {(file.file_size / 1024).toFixed(2)} KB • {new Date(file.uploaded_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <select
                          className="select select-bordered select-sm"
                          value={file.category_id || ''}
                          onChange={(e) => handleMoveToCategory(file.id, e.target.value ? Number(e.target.value) : null)}
                        >
                          <option value="">Move to...</option>
                          {categories.map((cat) => (
                            <option key={cat.id} value={cat.id}>{cat.name}</option>
                          ))}
                        </select>
                        <button
                          onClick={() => handleToggleActive(file.id, file.is_active)}
                          className={`btn btn-sm ${file.is_active ? 'btn-success' : 'btn-outline'}`}
                        >
                          {file.is_active ? 'Active' : 'Activate'}
                        </button>
                        <button
                          onClick={() => handleDeleteFile(file.id)}
                          className="btn btn-sm btn-error"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {getFilesForCategory(null).length === 0 && (
                <p className="text-gray-500 italic">No uncategorized files</p>
              )}
            </div>
          </div>

          {/* Categorized Files */}
          {categories.map((category) => (
            <div key={category.id} className="mb-6">
              <h3 className="text-lg font-semibold mb-2">{category.name}</h3>
              <div className="space-y-2">
                {getFilesForCategory(category.id).map((file) => (
                  <div key={file.id} className="card bg-base-200 shadow">
                    <div className="card-body p-4">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <p className="font-semibold">{file.original_filename}</p>
                          <p className="text-sm text-gray-500">
                            {(file.file_size / 1024).toFixed(2)} KB • {new Date(file.uploaded_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <select
                            className="select select-bordered select-sm"
                            value={file.category_id || ''}
                            onChange={(e) => handleMoveToCategory(file.id, e.target.value ? Number(e.target.value) : null)}
                          >
                            <option value="">Uncategorized</option>
                            {categories.map((cat) => (
                              <option key={cat.id} value={cat.id}>{cat.name}</option>
                            ))}
                          </select>
                          <button
                            onClick={() => handleToggleActive(file.id, file.is_active)}
                            className={`btn btn-sm ${file.is_active ? 'btn-success' : 'btn-outline'}`}
                          >
                            {file.is_active ? 'Active' : 'Activate'}
                          </button>
                          <button
                            onClick={() => handleDeleteFile(file.id)}
                            className="btn btn-sm btn-error"
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {getFilesForCategory(category.id).length === 0 && (
                  <p className="text-gray-500 italic">No files in this category</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
        </>
      )}

      {/* Configuration Tab Content */}
      {activeTab === 'config' && (
        <>
          <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
              <h2 className="card-title text-2xl mb-4">Custom Instructions</h2>
              <p className="text-sm text-gray-600 mb-4">
                Add custom rules and instructions that will guide the AI when teaching students.
                These instructions will be included in every conversation.
              </p>

              {/* Add Instruction Form */}
              <div className="card bg-base-200 p-4 mb-6">
                <h3 className="font-semibold mb-3">Add New Instruction</h3>
                <input
                  type="text"
                  placeholder="Instruction Name (e.g., 'Focus on Multiplication')"
                  className="input input-bordered mb-3 w-full"
                  value={newInstruction.name}
                  onChange={(e) => setNewInstruction({ ...newInstruction, name: e.target.value })}
                />
                <textarea
                  placeholder="Instruction text (e.g., 'Only ask multiplication questions between 1-12')"
                  className="textarea textarea-bordered mb-3 w-full h-24"
                  value={newInstruction.value}
                  onChange={(e) => setNewInstruction({ ...newInstruction, value: e.target.value })}
                />
                <button
                  className="btn btn-primary"
                  onClick={handleAddInstruction}
                  disabled={!newInstruction.name.trim() || !newInstruction.value.trim()}
                >
                  Add Instruction
                </button>
              </div>

              {/* Instructions List */}
              <div className="space-y-3">
                <h3 className="font-semibold text-lg">Active Instructions</h3>
                {instructions.length > 0 ? (
                  instructions.map((inst) => (
                    <div key={inst.id} className="card bg-base-200 shadow">
                      <div className="card-body p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <h4 className="font-bold text-lg">{inst.instruction_name}</h4>
                            <p className="text-sm mt-2 whitespace-pre-wrap">{inst.instruction_value}</p>
                            <p className="text-xs text-gray-500 mt-2">
                              Created: {new Date(inst.created_at).toLocaleDateString()}
                            </p>
                          </div>
                          <div className="flex gap-2">
                            <button
                              className={`btn btn-sm ${inst.is_active ? 'btn-success' : 'btn-outline'}`}
                              onClick={() => handleToggleInstruction(inst.id)}
                            >
                              {inst.is_active ? 'Active' : 'Inactive'}
                            </button>
                            <button
                              className="btn btn-sm btn-error"
                              onClick={() => handleDeleteInstruction(inst.id)}
                            >
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500 italic">No instructions yet. Add one above to customize the AI's behavior!</p>
                )}
              </div>
            </div>
          </div>

          {/* Info Card */}
          <div className="card bg-info text-info-content shadow-xl">
            <div className="card-body">
              <h3 className="card-title">How Custom Instructions Work</h3>
              <ul className="list-disc list-inside space-y-1">
                <li>Instructions are automatically included in every student conversation</li>
                <li>Active files and instructions work together to guide the AI</li>
                <li>Toggle instructions on/off to test different teaching approaches</li>
                <li>Changes apply to new conversations immediately</li>
              </ul>
            </div>
          </div>
        </>
      )}

      {/* Students Tab Content */}
      {activeTab === 'students' && (
        <div className="card bg-base-100 shadow-xl">
          <div className="card-body">
            <h2 className="card-title text-2xl mb-4">Student List</h2>

            {studentsLoading && (
              <div className="flex justify-center py-8">
                <span className="loading loading-spinner loading-lg"></span>
              </div>
            )}

            {studentsError && (
              <div className="alert alert-error">
                <span>{studentsError}</span>
              </div>
            )}

            {!studentsLoading && !studentsError && students.length === 0 && (
              <p className="text-gray-500 italic">No students registered yet.</p>
            )}

            {!studentsLoading && !studentsError && students.length > 0 && (
              <div className="overflow-x-auto">
                <table className="table table-zebra w-full">
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Full Name</th>
                      <th>Email</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map((student) => (
                      <tr key={student.username}>
                        <td>{student.username}</td>
                        <td>{student.full_name}</td>
                        <td>{student.email}</td>
                        <td>
                          <span className={`badge ${student.account_active ? 'badge-success' : 'badge-error'}`}>
                            {student.account_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Teacher;
