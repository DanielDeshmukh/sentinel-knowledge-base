import type { User } from '../types';

function ClassificationBadge({ value }: { value: User['role'] }) {
  return (
    <span className={`classification classification-${value}`}>
      <span />{value.toUpperCase()}
    </span>
  );
}

export default ClassificationBadge;
