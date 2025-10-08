import React, { useState, useEffect } from 'react';

interface Props {
  open: boolean;
  token: string;
  onClose: () => void;
  onSubmit: (token: string) => void;
  candidates: string[];
  loading: boolean;
  attempted: boolean;
}

const RetryDialog: React.FC<Props> = ({ open, token, onClose, onSubmit, candidates, loading, attempted }) => {
  const [value, setValue] = useState<string>(token);

  useEffect(() => {
    setValue(token);
  }, [token, open]);

  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(15, 23, 42, 0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: '16px',
          padding: '24px',
          width: '360px',
          boxShadow: '0 20px 40px rgba(15, 23, 42, 0.2)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ fontWeight: 700, fontSize: '16px' }}>再照合</div>
        <div style={{ fontSize: '14px', color: '#4b5563' }}>修正したいトークンを入力してください。</div>
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          style={{
            padding: '12px 16px',
            borderRadius: '12px',
            border: '1px solid #d1d5db',
            fontSize: '14px',
          }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 12px',
              borderRadius: '12px',
              border: '1px solid #d1d5db',
              background: '#fff',
              cursor: 'pointer',
            }}
          >
            キャンセル
          </button>
          <button
            onClick={() => onSubmit(value)}
            disabled={loading}
            style={{
              padding: '8px 12px',
              borderRadius: '12px',
              border: 'none',
              background: loading ? '#9ca3af' : '#1d4ed8',
              color: '#fff',
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
            }}
          >
            照合する
          </button>
        </div>
        <div style={{ minHeight: '40px', fontSize: '13px', color: '#1f2937' }}>
          {loading && '検索中...'}
          {!loading && attempted && candidates.length > 0 && (
            <div>
              <div style={{ marginBottom: '8px', color: '#1d4ed8', fontWeight: 600 }}>候補品番</div>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                {candidates.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}
          {!loading && attempted && candidates.length === 0 && '一致する候補は見つかりませんでした。'}
        </div>
      </div>
    </div>
  );
};

export default RetryDialog;
