import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import { ingestFile } from '../../services/api';
import type { Document, IngestionStage } from '../../types';

const pipelineSteps = [
  { id: 'upload', label: 'Upload' },
  { id: 'gate', label: 'Gate check' },
  { id: 'normalize', label: 'Normalize' },
  { id: 'recheck', label: 'Re-check' },
  { id: 'chunk', label: 'Chunk' },
  { id: 'embed', label: 'Embed' },
  { id: 'stage', label: 'Stage' },
  { id: 'promote', label: 'Promote' },
  { id: 'searchable', label: 'Searchable' },
];

function IngestionPanel() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [classification, setClassification] = useState<Document['classification']>('public');
  const [ingesting, setIngesting] = useState(false);
  const [ingestionStages, setIngestionStages] = useState<IngestionStage[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'text/markdown': ['.md'],
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxFiles: 1,
    maxSize: 5 * 1024 * 1024,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setSelectedFile(acceptedFiles[0]);
        setTitle((previous) => previous || acceptedFiles[0].name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '));
      }
    },
  });

  const handleIngest = async () => {
    if (!selectedFile || !title.trim()) {
      toast.error('Please select a file and provide a title');
      return;
    }

    setIngesting(true);
    setIngestionStages([]);

    try {
      const result = await ingestFile(selectedFile, title, classification);
      setIngestionStages(result.stages);
      if (result.status === 'completed') {
        toast.success('Document ingested successfully!');
        queryClient.invalidateQueries({ queryKey: ['documents'] });
        setTitle('');
        setSelectedFile(null);
      } else {
        toast.error('Ingestion failed');
      }
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Ingestion failed');
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="ingestion-layout">
      <div className="ingestion-form panel">
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #2a2a2a' }}>
          <strong style={{ fontSize: '12px' }}>UPLOAD DOCUMENT</strong>
          <span style={{ color: '#777', font: '500 8px IBM Plex Mono, monospace', marginLeft: '8px' }}>REQUIRED FIELDS</span>
        </div>
        <div style={{ padding: '24px' }}>
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '9px', color: '#858585', fontFamily: 'IBM Plex Mono, monospace', letterSpacing: '.06em' }}>
              TITLE
            </label>
            <input
              type="text"
              value={title}
              onChange={(event) => setTitle(event.currentTarget.value)}
              placeholder="Document title"
            />
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', marginBottom: '6px', fontSize: '9px', color: '#858585', fontFamily: 'IBM Plex Mono, monospace', letterSpacing: '.06em' }}>
              CLASSIFICATION
            </label>
            <select
              value={classification}
              onChange={(event) => {
                const value = event.currentTarget.value;
                if (value === 'public' || value === 'internal' || value === 'restricted') {
                  setClassification(value);
                }
              }}
            >
              <option value="public">Public</option>
              <option value="internal">Internal</option>
              <option value="restricted">Restricted</option>
            </select>
          </div>

          <div
            {...getRootProps()}
            style={{
              padding: '40px',
              border: `1px dashed ${isDragActive ? '#a0a09d' : '#303030'}`,
              textAlign: 'center',
              cursor: 'pointer',
              transition: 'border-color 0.2s',
              background: isDragActive ? '#1a1a1a' : '#161616',
            }}
          >
            <input {...getInputProps()} />
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ color: '#777', marginBottom: '12px' }}><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            <p style={{ color: '#a5a5a5', fontSize: '12px', marginBottom: '4px' }}>
              {selectedFile ? selectedFile.name : isDragActive ? 'Drop file here' : 'Drag & drop a file here'}
            </p>
            <p style={{ fontSize: '10px', color: '#777', marginTop: '8px' }}>
              MD, PDF, DOCX — max 5MB
            </p>
          </div>

          <button
            className="btn-primary"
            onClick={handleIngest}
            disabled={ingesting || !selectedFile || !title.trim()}
            style={{ width: '100%', marginTop: '20px' }}
          >
            {ingesting ? 'PROCESSING...' : 'START INGESTION'}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
          </button>
        </div>
      </div>

      <div className="pipeline-panel panel">
        <div style={{ padding: '20px 24px', borderBottom: '1px solid #2a2a2a' }}>
          <strong style={{ fontSize: '12px' }}>INGESTION PIPELINE</strong>
          <span style={{ color: '#777', font: '500 8px IBM Plex Mono, monospace', marginLeft: '8px' }}>9 STAGES</span>
        </div>
        <div style={{ padding: '24px' }}>
          <div className="pipeline-list">
            {pipelineSteps.map((step, index) => {
              const stage = ingestionStages.find((item) => item.stage === step.id);
              const status = stage?.status || 'pending';
              return (
                <div key={step.id} className={`pipeline-step step-${status}`}>
                  <div className="step-track">
                    <div className="step-indicator">{index + 1}</div>
                    {index < pipelineSteps.length - 1 && <i />}
                  </div>
                  <div className="step-body">
                    <div>
                      <strong>{step.label}</strong>
                      {stage?.timing_ms !== undefined && stage?.timing_ms !== null && (
                        <span>{Math.round(stage.timing_ms)}ms</span>
                      )}
                    </div>
                    {stage?.message && <p>{stage.message}</p>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

export default IngestionPanel;
