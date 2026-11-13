import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { getAccessRequests, reviewAccessRequest } from '../services/api';
import type { User } from '../types';
import RoleDropdown, { type AssignableRole } from '../components/RoleDropdown';
import { useState } from 'react';

function AccessRequestRow({ request, onReview, busy }: { request: User; onReview: (id: string, role: AssignableRole) => void; busy: boolean }) {
  const [role, setRole] = useState<AssignableRole>(request.requested_role ?? 'public');
  return <article className="access-request-card">
    <div className="access-request-identity">
      <span className="access-avatar">{request.display_name.slice(0, 1).toUpperCase()}</span>
      <div><h2>{request.display_name}</h2><p>{request.email}</p></div>
      <span className="access-status">PENDING REVIEW</span>
    </div>
    <div className="access-request-details">
      <div><span className="access-detail-label">REQUESTED ROLE</span><strong>{request.requested_role ?? 'Public'}</strong></div>
      <div><span className="access-detail-label">CURRENT ACCESS</span><strong>{request.role}</strong></div>
      <RoleDropdown label="Assign final role" value={role} onChange={setRole} />
    </div>
    <button className="btn-primary access-approve" disabled={busy} onClick={() => onReview(request.id, role)}>
      {busy ? 'SAVING…' : `ASSIGN ${role.toUpperCase()} & CLOSE REQUEST`}
    </button>
  </article>;
}

export default function AccessControl() {
  const client = useQueryClient();
  const { data: requests = [], isLoading, isError } = useQuery({ queryKey: ['access-requests'], queryFn: getAccessRequests });
  const mutation = useMutation({
    mutationFn: ({ id, role }: { id: string; role: AssignableRole }) => reviewAccessRequest(id, role),
    onSuccess: () => { client.invalidateQueries({ queryKey: ['access-requests'] }); client.invalidateQueries({ queryKey: ['users'] }); toast.success('Role assigned and request reviewed'); },
    onError: () => toast.error('Could not update this access request'),
  });
  return <>
    <div className="inner-page-heading"><div><div className="section-kicker"><span>04</span> / IDENTITY OPERATIONS</div>
      <h1>Access requests<span className="heading-period">.</span></h1><p>Review each request and assign the access this account should have.</p></div>
      <span className="badge">ADMIN ONLY</span></div>
    {isLoading ? <div className="loading">LOADING ACCESS REQUESTS</div> : isError ? <p className="access-empty">Could not load access requests. Please refresh.</p> : requests.length === 0 ?
      <div className="access-empty"><strong>Queue clear</strong><p>No pending role requests.</p></div> :
      <div className="access-request-list">{requests.map((request) => <AccessRequestRow key={request.id} request={request} busy={mutation.isPending} onReview={(id, role) => mutation.mutate({ id, role })} />)}</div>}
  </>;
}
