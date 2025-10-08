import React from 'react';
import { FailureRow } from '../api';

interface Props {
  rows: FailureRow[];
  onRetry: (token: string) => void;
}

const FailuresTable: React.FC<Props> = ({ rows, onRetry }) => {
  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>PDF</th>
            <th>ページ</th>
            <th>トークン</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr className="failure-row">
              <td colSpan={4} style={{ textAlign: 'center', padding: '24px', color: '#b91c1c' }}>
                失敗データはありません。
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr className="failure-row" key={`${row.pdf_name}-${row.page}-${row.token}-${index}`}>
                <td>{row.pdf_name}</td>
                <td>{row.page}</td>
                <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ display: 'inline-flex', width: '8px', height: '8px', borderRadius: '9999px', background: '#dc2626' }} />
                  {row.token}
                </td>
                <td>
                  <button
                    onClick={() => onRetry(row.token)}
                    style={{
                      background: '#1d4ed8',
                      color: '#fff',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      cursor: 'pointer',
                      boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                    }}
                  >
                    再照合
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};

export default FailuresTable;
