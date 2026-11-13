import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getUsers, updateUserRole, deleteDocument, getDocuments } from '../services/api';
import type { Document, RoleUpdate, User } from '../types';
import toast from 'react-hot-toast';
import DocumentLibrary from '../components/admin/DocumentLibrary';
import IngestionPanel from '../components/admin/IngestionPanel';
import UserDirectory from '../components/admin/UserDirectory';

const Admin: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'users' | 'ingest'>('ingest');
  const queryClient = useQueryClient();

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  });

  const { data: documents, isLoading: docsLoading } = useQuery({
    queryKey: ['documents'],
    queryFn: getDocuments,
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: RoleUpdate['role'] }) =>
      updateUserRole(userId, { role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('Role updated');
    },
    onError: () => toast.error('Failed to update role'),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      toast.success('Document deleted');
    },
    onError: () => toast.error('Failed to delete document'),
  });

  const handleRoleChange = (userId: string, role: User['role']) => {
    roleMutation.mutate({ userId, role });
  };

  const handleDeleteDocument = (document: Document) => {
    if (window.confirm(`Delete "${document.title}"?`)) {
      deleteMutation.mutate(document.id);
    }
  };

  return (
    <section className="admin-page">
      <header className="inner-page-heading">
        <div>
          <div className="section-kicker">KNOWLEDGE OPERATIONS</div>
          <h1>Ingest a document<span className="heading-period">.</span></h1>
          <p>Validate, index, and publish a corpus record for authorized chat.</p>
        </div>
        <span className="badge">ADMIN WORKSPACE</span>
      </header>

      <div className="admin-tabs" role="tablist" aria-label="Admin workspace">
        <button
          onClick={() => setActiveTab('ingest')}
          className={`text-action ${activeTab === 'ingest' ? 'active' : ''}`}
          role="tab"
          aria-selected={activeTab === 'ingest'}
          aria-controls="admin-ingestion-panel"
          style={{
            borderBottom: activeTab === 'ingest' ? '2px solid #f0f0ed' : '2px solid transparent',
            paddingBottom: '10px',
            color: activeTab === 'ingest' ? '#f0f0ed' : '#777',
          }}
        >
          Ingestion
        </button>
        <button
          onClick={() => setActiveTab('users')}
          className={`text-action ${activeTab === 'users' ? 'active' : ''}`}
          role="tab"
          aria-selected={activeTab === 'users'}
          aria-controls="admin-users-panel"
          style={{
            borderBottom: activeTab === 'users' ? '2px solid #f0f0ed' : '2px solid transparent',
            paddingBottom: '10px',
            color: activeTab === 'users' ? '#f0f0ed' : '#777',
          }}
        >
          Users
        </button>
      </div>

      <div id="admin-users-panel" role="tabpanel" tabIndex={0} hidden={activeTab !== 'users'} className="admin-user-panel">
        <UserDirectory
          users={users}
          isLoading={usersLoading}
          onRoleChange={handleRoleChange}
        />
      </div>
      <div id="admin-ingestion-panel" role="tabpanel" tabIndex={0} hidden={activeTab !== 'ingest'} className="admin-ingestion-content">
        <section className="admin-ingestion-section" aria-labelledby="ingestion-section-title">
          <div className="admin-section-heading"><h2 id="ingestion-section-title">New corpus record</h2><p>Required source and classification details, followed by live parser and vector status.</p></div>
          <IngestionPanel />
        </section>
        <DocumentLibrary
          documents={documents}
          isLoading={docsLoading}
          onDelete={handleDeleteDocument}
        />
      </div>
    </section>
  );
};

export default Admin;
