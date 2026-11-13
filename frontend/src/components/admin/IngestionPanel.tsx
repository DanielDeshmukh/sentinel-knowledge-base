import { useCallback, useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useDropzone } from 'react-dropzone';
import toast from 'react-hot-toast';
import {
  getCorpusJob,
  ingestFile,
  CorpusIngestionStreamError,
} from '../../services/api';
import type {
  CorpusDiagnostic,
  CorpusJobSnapshot,
  CorpusMetadata,
  CorpusProgressEvent,
  CorpusStage,
  Document,
} from '../../types';

const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const pipelineSteps: { id: CorpusStage; label: string }[] = [
  { id: 'upload', label: 'Upload and type check' },
  { id: 'parse', label: 'Extract text' },
  { id: 'regex_validate', label: 'Shared corpus rules' },
  { id: 'normalize', label: 'Normalize' },
  { id: 'recheck', label: 'Re-check rules' },
  { id: 'chunk', label: 'Chunk' },
  { id: 'embed', label: 'Generate embeddings' },
  { id: 'stage_vectors', label: 'Stage pgvector rows' },
  { id: 'promote', label: 'Commit to pgvector' },
  { id: 'searchable', label: 'Available in chat' },
];

function recoveredEvent(job: CorpusJobSnapshot): CorpusProgressEvent {
  return {
    ...job.progress,
    job_id: job.id,
    sequence: job.sequence,
    stage: job.stage,
    status: job.status === 'running' ? 'running' : job.status === 'succeeded' ? 'completed' : 'failed',
    timing_ms: job.progress.timing_ms ?? null,
    message: job.progress.message ?? (job.status === 'succeeded'
      ? 'Document is searchable in role-authorized chat'
      : 'Ingestion progress recovered from the server'),
    terminal: job.status !== 'running',
    diagnostics: job.diagnostics,
    error_code: job.error_code ?? undefined,
  };
}

function IngestionPanel() {
  const queryClient = useQueryClient();
  const [title, setTitle] = useState('');
  const [classification, setClassification] = useState<Document['classification']>('public');
  const [sourceUrls, setSourceUrls] = useState('');
  const [retrievedAt, setRetrievedAt] = useState(new Date().toISOString().slice(0, 10));
  const [reuseBasis, setReuseBasis] = useState('');
  const [synthetic, setSynthetic] = useState(false);
  const [syntheticLabel, setSyntheticLabel] = useState('');
  const [ingesting, setIngesting] = useState(false);
  const [events, setEvents] = useState<CorpusProgressEvent[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(() => localStorage.getItem('activeCorpusJobId'));

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      'text/markdown': ['.md'],
      'text/plain': ['.md'],
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    },
    maxFiles: 1,
    maxSize: MAX_UPLOAD_BYTES,
    onDrop: (acceptedFiles) => {
      if (acceptedFiles.length > 0) {
        setSelectedFile(acceptedFiles[0]);
        setTitle((previous) => previous || acceptedFiles[0].name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '));
      }
    },
    onDropRejected: (rejections) => {
      const tooLarge = rejections.some((rejection) => rejection.errors.some((error) => error.code === 'file-too-large'));
      toast.error(tooLarge ? 'File exceeds the 4 MB upload limit' : 'Choose one MD, PDF, or DOCX file');
    },
  });

  const onEvent = useCallback((event: CorpusProgressEvent) => {
    localStorage.setItem('activeCorpusJobId', event.job_id);
    setActiveJobId(event.job_id);
    setEvents((previous) => {
      const lastSequence = Math.max(0, ...previous.filter((item) => item.job_id === event.job_id).map((item) => item.sequence));
      if (event.sequence <= lastSequence) return previous;
      const next = previous.filter((item) => item.stage !== event.stage);
      return [...next, event];
    });
    if (event.terminal) {
      localStorage.removeItem('activeCorpusJobId');
      setActiveJobId(null);
    }
  }, []);

  useEffect(() => {
    if (!activeJobId) return undefined;
    let active = true;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const snapshot = await getCorpusJob(activeJobId);
        if (!active) return;
        onEvent(recoveredEvent(snapshot));
        if (snapshot.status === 'succeeded' && snapshot.stage === 'searchable') {
          localStorage.removeItem('activeCorpusJobId');
          setActiveJobId(null);
          await queryClient.invalidateQueries({ queryKey: ['documents'] });
        } else if (snapshot.status === 'failed') {
          localStorage.removeItem('activeCorpusJobId');
          setActiveJobId(null);
        } else {
          timer = window.setTimeout(poll, 2000);
        }
      } catch {
        if (active) timer = window.setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [activeJobId, queryClient, onEvent]);

  const recoverJob = async (jobId: string) => {
    let snapshot = await getCorpusJob(jobId);
    onEvent(recoveredEvent(snapshot));
    for (let attempt = 0; snapshot.status === 'running' && attempt < 120; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
      snapshot = await getCorpusJob(jobId);
      onEvent(recoveredEvent(snapshot));
    }
    return snapshot;
  };

  const handleIngest = async () => {
    if (!selectedFile || !title.trim()) {
      toast.error('Select a file and provide a title');
      return;
    }
    if (selectedFile.size > MAX_UPLOAD_BYTES) {
      toast.error('File exceeds the 4 MB upload limit');
      return;
    }
    if (!reuseBasis.trim() || (!synthetic && !sourceUrls.trim())) {
      if (synthetic) {
        toast.error('Add a reuse basis describing the original synthetic work. Source URLs are not needed.');
      } else {
        const missingFields = [
          !sourceUrls.trim() ? 'at least one source URL' : '',
          !reuseBasis.trim() ? 'a reuse basis' : '',
        ].filter(Boolean);
        toast.error(`Add ${missingFields.join(' and ')} to continue.`);
      }
      return;
    }
    if ((classification === 'public' && synthetic) || (classification !== 'public' && !synthetic)) {
      toast.error('Public records need source provenance; internal and restricted records must be marked synthetic');
      return;
    }
    if (synthetic && sourceUrls.trim()) {
      toast.error('Synthetic records cannot include source URLs');
      return;
    }
    if (synthetic && !syntheticLabel.trim()) {
      toast.error('Add the required label for synthetic content');
      return;
    }

    const metadata: CorpusMetadata = {
      title: title.trim(),
      classification,
      sourceUrls: synthetic ? [] : sourceUrls.split(/\r?\n/).map((url) => url.trim()).filter(Boolean),
      retrievedAt: synthetic ? '' : retrievedAt,
      reuseBasis: reuseBasis.trim(),
      synthetic,
      syntheticLabel: synthetic ? syntheticLabel.trim() : '',
    };
    setIngesting(true);
    setEvents([]);

    try {
      const result = await ingestFile(selectedFile, metadata, onEvent);
      if (result.stage === 'searchable' && result.status === 'completed') {
        toast.success('Corpus synced to pgvector and available in role-authorized chat');
        await queryClient.invalidateQueries({ queryKey: ['documents'] });
        setTitle('');
        setSelectedFile(null);
      } else {
        toast.error(result.message || 'Corpus ingestion failed');
      }
    } catch (error) {
      if (error instanceof CorpusIngestionStreamError && error.jobId) {
        try {
          const job = await recoverJob(error.jobId);
          if (job.status === 'succeeded' && job.stage === 'searchable') {
            toast.success('Sync completed; status recovered from the server');
            await queryClient.invalidateQueries({ queryKey: ['documents'] });
            setSelectedFile(null);
            setTitle('');
          } else if (job.status === 'failed') {
            toast.error(job.progress.message || 'Corpus ingestion failed');
          } else {
            toast.error('Ingestion is still running. Its status remains available in the pipeline.');
          }
        } catch {
          toast.error('Connection interrupted; could not recover the ingestion status');
        }
      } else {
        toast.error(error instanceof Error ? error.message : 'Ingestion failed');
      }
    } finally {
      setIngesting(false);
    }
  };

  const latestEvent = events[events.length - 1];
  const diagnostics = Array.from(new Map(
    events.flatMap((event) => event.diagnostics || []).map((item) => [`${item.code}-${item.line}`, item as CorpusDiagnostic]),
  ).values());
  const searchable = events.find((event) => event.stage === 'searchable' && event.status === 'completed');

  return (
    <div className="ingestion-layout">
      <div className="ingestion-form panel">
        <div className="ingestion-panel-heading">
          <h3>Record details</h3>
          <p>Enter source and access metadata before syncing.</p>
        </div>
        <div className="ingestion-form-body">
          <div className="ingestion-fields-grid">
          <label className="corpus-field">TITLE
            <input value={title} onChange={(event) => setTitle(event.currentTarget.value)} placeholder="Document title" />
          </label>
          <label className="corpus-field">CLASSIFICATION
            <select value={classification} onChange={(event) => setClassification(event.currentTarget.value as Document['classification'])}>
              <option value="public">Public</option>
              <option value="internal">Internal</option>
              <option value="restricted">Restricted</option>
            </select>
          </label>
          {!synthetic && <label className="corpus-field corpus-field-wide">SOURCE URLS <span>(one per line)</span>
            <textarea rows={3} value={sourceUrls} onChange={(event) => setSourceUrls(event.currentTarget.value)} placeholder="https://example.org/source" />
          </label>}
          {!synthetic && <label className="corpus-field">RETRIEVED DATE
            <input type="date" value={retrievedAt} onChange={(event) => setRetrievedAt(event.currentTarget.value)} />
          </label>}
          <label className="corpus-field corpus-field-wide">REUSE BASIS
            <textarea rows={3} value={reuseBasis} onChange={(event) => setReuseBasis(event.currentTarget.value)} placeholder={synthetic ? 'Describe the original synthetic work performed' : "Describe the source's license or the original work performed"} />
            <span className="corpus-field-help">Required for every record. Synthetic records do not need source URLs or a retrieved date.</span>
          </label>
          <label className="corpus-checkbox">
            <input type="checkbox" checked={synthetic} onChange={(event) => {
              const checked = event.currentTarget.checked;
              setSynthetic(checked);
              if (checked) {
                setSourceUrls('');
                setRetrievedAt('');
              } else if (!retrievedAt) {
                setRetrievedAt(new Date().toISOString().slice(0, 10));
              }
            }} />
            This is synthetic content
          </label>
          {synthetic && <label className="corpus-field">SYNTHETIC LABEL
            <input value={syntheticLabel} onChange={(event) => setSyntheticLabel(event.currentTarget.value)} placeholder="SYNTHETIC: for demonstration only" />
          </label>}
          </div>

          <div className="ingestion-dropzone" {...getRootProps()} style={{ padding: '20px', border: `1px dashed ${isDragActive ? '#a0a09d' : '#303030'}`, textAlign: 'center', cursor: 'pointer', background: isDragActive ? '#1a1a1a' : '#161616' }}>
            <input {...getInputProps()} />
            <p style={{ color: '#a5a5a5', fontSize: '12px', marginBottom: '4px' }}>
              {selectedFile ? selectedFile.name : isDragActive ? 'Drop file here' : 'Drag & drop a file here'}
            </p>
            <p style={{ fontSize: '10px', color: '#777', marginTop: '8px' }}>MD, PDF, DOCX — max 4 MB</p>
          </div>

          <button className="btn-primary ingestion-submit" onClick={handleIngest} disabled={ingesting || Boolean(activeJobId) || !selectedFile || !title.trim()}>
            {ingesting || activeJobId ? 'SYNCING TO PGVECTOR…' : 'VALIDATE AND SYNC'}
          </button>
        </div>
      </div>

      <div className="pipeline-panel panel">
        <div className="ingestion-panel-heading">
          <h3>Sync progress</h3>
          <p>Parser, embedding, and pgvector status.</p>
        </div>
        <div className="pipeline-panel-body" aria-label="Corpus sync pipeline">
          <div className="pipeline-list" aria-live="polite">
            {pipelineSteps.map((step, index) => {
              const stage = events.find((item) => item.stage === step.id);
              const status = stage?.status || 'pending';
              return (
                <div key={step.id} className={`pipeline-step step-${status}`}>
                  <div className="step-track"><div className="step-indicator">{index + 1}</div>{index < pipelineSteps.length - 1 && <i />}</div>
                  <div className="step-body">
                    <div><strong>{step.label}</strong>{stage?.timing_ms != null && <span>{Math.round(stage.timing_ms)}ms</span>}</div>
                    {stage?.message && <p>{stage.message}</p>}
                    {(stage?.stage === 'embed' || stage?.stage === 'stage_vectors') && stage.total != null && (
                      <p>{stage.stage === 'embed' ? 'Embedded' : 'Vectors written'}: {stage.stage === 'stage_vectors' ? stage.vectors_written ?? stage.completed ?? 0 : stage.completed ?? 0} / {stage.total}</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          {latestEvent?.status === 'failed' && <p role="alert">{latestEvent.error_code}: {latestEvent.message}</p>}
          {diagnostics.length > 0 && <div role="status" aria-label="Corpus parser diagnostics">
            <strong>Parser diagnostics</strong>
            <ul>{diagnostics.map((item, index) => <li key={`${item.code}-${index}`}>{item.severity}: {item.message}{item.line ? ` (line ${item.line})` : ''}</li>)}</ul>
          </div>}
          {searchable && <p role="status">Searchable in chat since {searchable.searchable_at ? new Date(searchable.searchable_at).toLocaleString() : 'just now'}; access follows the selected classification.</p>}
        </div>
      </div>
    </div>
  );
}

export default IngestionPanel;
