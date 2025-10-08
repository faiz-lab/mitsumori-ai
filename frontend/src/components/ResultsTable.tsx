import React from 'react';
import { ResultRow } from '../api';

interface Props {
  rows: ResultRow[];
}

const ResultsTable: React.FC<Props> = ({ rows }) => {
  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            <th>PDF</th>
            <th>ページ</th>
            <th>トークン</th>
            <th>マッチ種別</th>
            <th>品番</th>
            <th>在庫</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr className="table-row">
              <td colSpan={6} style={{ textAlign: 'center', padding: '24px', color: '#6b7280' }}>
                データがありません。
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr className="table-row" key={`${row.pdf_name}-${row.page}-${row.token}-${index}`}>
                <td>{row.pdf_name}</td>
                <td>{row.page}</td>
                <td>{row.token}</td>
                <td style={{ textTransform: 'uppercase', fontWeight: 600, color: row.matched_type === 'hinban' ? '#1d4ed8' : '#2563eb' }}>
                  {row.matched_type}
                </td>
                <td>{row.matched_hinban}</td>
                <td>{row.zaiko ?? ''}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
};

export default ResultsTable;
