import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { getUsers, reviewAccessRequest, updateUserRole } from '../services/api';
import type { User } from '../types';
import RoleDropdown, { type AssignableRole } from '../components/RoleDropdown';

function AccessUserRow({
  user,
  onSave,
  busy,
}: {
  user: User;
  onSave: (user: User, role: AssignableRole) => void;
  busy: boolean;
}) {
  const assignedRole: AssignableRole = user.role === 'admin' ? 'public' : user.role;
  const [role, setRole] = useState<AssignableRole>(assignedRole);
  const hasPendingRequest = user.role_request_status === 'pending';
  const changed = role !== assignedRole;

  return (
    <article className={`access-user-row${hasPendingRequest ? ' has-pending-request' : ''}`}>
      <div className="access-user-identity">
        <span className="access-avatar" aria-hidden="true">{user.display_name.slice(0, 1).toUpperCase()}</span>
        <div className="access-user-name">
          <h2>{user.display_name}</h2>
          <p>{user.email}</p>
        </div>
      </div>

      <div className="access-user-current">
        <span className="access-detail-label">CURRENT ROLE</span>
        <strong>{user.role}</strong>
      </div>

      <div className="access-user-request">
        <span className="access-detail-label">ROLE REQUEST</span>
        {hasPendingRequest ? (
          <strong>{user.requested_role ?? 'Not specified'} <span className="access-status">Needs review</span></strong>
        ) : user.role_request_status === 'reviewed' ? (
          <strong>{user.requested_role ?? 'Role request'} <span className="access-reviewed">Reviewed</span></strong>
        ) : (
          <span className="access-no-request">No request</span>
        )}
      </div>

      <div className="access-user-action">
        {user.role === 'admin' ? (
          <span className="access-admin-note">Admin account</span>
        ) : (
          <>
            <RoleDropdown
              label={hasPendingRequest ? 'Assign final role' : 'Change role'}
              value={role}
              onChange={setRole}
            />
            <button
              className="btn-primary access-approve"
              disabled={busy || (!hasPendingRequest && !changed)}
              onClick={() => onSave(user, role)}
            >
              {busy ? 'SAVING…' : hasPendingRequest ? 'REVIEW REQUEST' : changed ? 'SAVE ROLE' : 'ROLE UP TO DATE'}
            </button>
          </>
        )}
      </div>
    </article>
  );
}

export default function AccessControl() {
  const client = useQueryClient();
  const { data: users = [], isLoading, isError } = useQuery({ queryKey: ['users'], queryFn: getUsers });
  const sortedUsers = useMemo(() => [...users].sort((left, right) => {
    const requestOrder = Number(right.role_request_status === 'pending') - Number(left.role_request_status === 'pending');
    return requestOrder || left.display_name.localeCompare(right.display_name);
  }), [users]);

  const mutation = useMutation({
    mutationFn: ({ user, role }: { user: User; role: AssignableRole }) =>
      user.role_request_status === 'pending'
        ? reviewAccessRequest(user.id, role)
        : updateUserRole(user.id, { role }),
    onSuccess: (_updatedUser, variables) => {
      client.invalidateQueries({ queryKey: ['users'] });
      client.invalidateQueries({ queryKey: ['access-requests'] });
      toast.success(variables.user.role_request_status === 'pending' ? 'Request reviewed and role assigned' : 'User role updated');
    },
    onError: () => toast.error('Could not update this user’s role'),
  });

  const pendingCount = users.filter((user) => user.role_request_status === 'pending').length;

  return (
    <>
      <div className="inner-page-heading">
        <div>
          <div className="section-kicker"><span>04</span> / IDENTITY OPERATIONS</div>
          <h1>User access<span className="heading-period">.</span></h1>
          <p>Review role requests and manage access for every account.</p>
        </div>
        <span className="badge">ADMIN ONLY</span>
      </div>

      <section className="access-directory" aria-label="User access directory">
        <header className="access-directory-heading">
          <div>
            <h2>All users</h2>
            <p>Pending requests appear first. Role changes take effect immediately.</p>
          </div>
          <div className="access-directory-counts" aria-label={`${users.length} users, ${pendingCount} requests to review`}>
            <span><strong>{users.length}</strong> users</span>
            <span><strong>{pendingCount}</strong> to review</span>
          </div>
        </header>

        {isLoading ? (
          <div className="loading">LOADING USERS</div>
        ) : isError ? (
          <div className="access-empty"><strong>Could not load users</strong><p>Refresh the page to try again.</p></div>
        ) : users.length === 0 ? (
          <div className="access-empty"><strong>No user accounts yet</strong><p>New registrations will appear here.</p></div>
        ) : (
          <div className="access-user-list">
            {sortedUsers.map((user) => (
              <AccessUserRow
                key={`${user.id}:${user.role}`}
                user={user}
                busy={mutation.isPending}
                onSave={(selectedUser, role) => mutation.mutate({ user: selectedUser, role })}
              />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
