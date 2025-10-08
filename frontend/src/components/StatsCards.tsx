import React from 'react';
import { StatusTotals } from '../api';

interface Props {
  totals: StatusTotals;
}

const StatsCards: React.FC<Props> = ({ totals }) => {
  const items = [
    { label: '総トークン数', value: totals.tokens },
    { label: '品番ヒット', value: totals.hit_hinban },
    { label: '仕様ヒット', value: totals.hit_spec },
    { label: '失敗数', value: totals.fail },
  ];
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '12px',
      }}
    >
      {items.map((item) => (
        <div
          key={item.label}
          style={{
            background: '#fff',
            borderRadius: '12px',
            padding: '16px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          }}
        >
          <div style={{ fontSize: '12px', color: '#6b7280' }}>{item.label}</div>
          <div style={{ fontSize: '20px', fontWeight: 700, marginTop: '4px' }}>{item.value}</div>
        </div>
      ))}
    </div>
  );
};

export default StatsCards;
