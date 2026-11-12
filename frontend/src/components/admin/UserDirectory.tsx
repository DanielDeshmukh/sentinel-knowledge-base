import type { User } from '../../types';
import ClassificationBadge from '../ClassificationBadge';

const roleOptions = ['public', 'internal', 'restricted', 'admin'] as const;

interface UserDirectoryProps {
  users: User[] | undefined;
  isLoading: boolean;
  onRoleChange: (userId: string, role: User['role']) => void;
}

function UserDirectory({ users, isLoading, onRoleChange }: UserDirectoryProps) {
  return (
    <div>
      <div className="table-heading">
        <div>
          <div className="section-kicker"><span>01</span> / USER DIRECTORY</div>
          <h2>Manage users <span style={{ font: '500 10px IBM Plex Mono, monospace', color: '#707070', marginLeft: '6px', verticalAlign: '3px' }}>{String(users?.length || 0).padStart(2, '0')}</span></h2>
        </div>
      </div>

      {isLoading ? (
        <div className="loading">LOADING USERS</div>
      ) : (
        <div className="document-table">
          <div className="document-table-head">
            <span>USER</span>
            <span>ROLE</span>
            <span>STATUS</span>
            <span />
          </div>
          {users?.map((user) => (
            <div className="document-row" key={user.id}>
              <div className="document-name">
                <span className="file-icon" style={{ background: '#343434', color: '#f4f4f0', border: '1px solid #4a4a4a', display: 'grid', placeItems: 'center', width: '34px', height: '34px', fontSize: '11px', fontWeight: 600 }}>
                  {user.display_name.charAt(0).toUpperCase()}
                </span>
                <span>
                  <strong>{user.display_name}</strong>
                  <small>{user.email}</small>
                  <small>Joined {new Date(user.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</small>
                </span>
              </div>
              <ClassificationBadge value={user.role} />
              <span className="table-muted">
                {user.approved ? 'APPROVED' : 'PENDING'}
              </span>
              <div className="row-actions">
                <select
                  value={user.role}
                  onChange={(event) => {
                    const role = roleOptions.find((option) => option === event.currentTarget.value);
                    if (role) onRoleChange(user.id, role);
                  }}
                  style={{
                    minWidth: '110px',
                    background: '#171717',
                    border: '1px solid #303030',
                    padding: '6px 8px',
                    color: '#ddd',
                    fontSize: '10px',
                    fontFamily: 'IBM Plex Mono, monospace',
                  }}
                >
                  <option value="public">Public</option>
                  <option value="internal">Internal</option>
                  <option value="restricted">Restricted</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default UserDirectory;
