import { useState } from 'react';

export type AssignableRole = 'public' | 'internal' | 'restricted';
const roles: { value: AssignableRole; label: string; detail: string }[] = [
  { value: 'public', label: 'Public', detail: 'Public knowledge only' },
  { value: 'internal', label: 'Internal', detail: 'Public and internal knowledge' },
  { value: 'restricted', label: 'Restricted', detail: 'All classified knowledge' },
];

export default function RoleDropdown({ value, onChange, label = 'Requested access level' }: {
  value: AssignableRole; onChange: (value: AssignableRole) => void; label?: string;
}) {
  const [open, setOpen] = useState(false);
  const selected = roles.find((role) => role.value === value) ?? roles[0];
  return (
    <div className="role-picker">
      <span className="role-picker-label">{label}</span>
      <button type="button" className="role-picker-trigger" aria-haspopup="listbox" aria-expanded={open}
        onClick={() => setOpen((current) => !current)} onKeyDown={(event) => {
          if (event.key === 'Escape') setOpen(false);
          if (event.key === 'ArrowDown' && !open) { event.preventDefault(); setOpen(true); }
        }}>
        <span><strong>{selected.label}</strong><small>{selected.detail}</small></span>
        <span aria-hidden="true">{open ? '−' : '+'}</span>
      </button>
      {open && <div className="role-picker-options" role="listbox" aria-label={label}>
        {roles.map((role) => <button type="button" role="option" aria-selected={role.value === value} key={role.value}
          className="role-picker-option" onClick={() => { onChange(role.value); setOpen(false); }}>
          <span><strong>{role.label}</strong><small>{role.detail}</small></span>
          {role.value === value && <span aria-hidden="true">✓</span>}
        </button>)}
      </div>}
    </div>
  );
}
