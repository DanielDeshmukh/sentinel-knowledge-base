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
    <>
      <div className="inner-page-heading">
        <div>
          <div className="section-kicker"><span>03</span> / KNOWLEDGE OPERATIONS</div>
          <h1>Ingest a document<span className="heading-period">.</span></h1>
          <p>From raw file to searchable knowledge, with every step in view.</p>
        </div>
        <span className="badge">ADMIN WORKSPACE</span>
      </div>

      <div style={{ display: 'flex', gap: '0', marginBottom: '30px' }}>
        <button
          onClick={() => setActiveTab('ingest')}
          className={`text-action ${activeTab === 'ingest' ? 'active' : ''}`}
          style={{
            borderBottom: activeTab === 'ingest' ? '2px solid #f0f0ed' : '2px solid transparent',
            paddingBottom: '10px',
            marginRight: '24px',
            color: activeTab === 'ingest' ? '#f0f0ed' : '#777',
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          INGESTION
        </button>
        <button
          onClick={() => setActiveTab('users')}
          className={`text-action ${activeTab === 'users' ? 'active' : ''}`}
          style={{
            borderBottom: activeTab === 'users' ? '2px solid #f0f0ed' : '2px solid transparent',
            paddingBottom: '10px',
            color: activeTab === 'users' ? '#f0f0ed' : '#777',
          }}
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></svg>
          USERS
        </button>
      </div>

      <div hidden={activeTab !== 'ingest'}>
        <IngestionPanel />
      </div>
      {activeTab === 'users' && (
        <UserDirectory
          users={users}
          isLoading={usersLoading}
          onRoleChange={handleRoleChange}
        />
      )}
      <div hidden={activeTab !== 'ingest'}>
        <DocumentLibrary
          documents={documents}
          isLoading={docsLoading}
          onDelete={handleDeleteDocument}
        />
      </div>
    </>
  );
};

export default Admin;
