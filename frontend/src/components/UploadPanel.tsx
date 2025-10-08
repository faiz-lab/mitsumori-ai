import React from 'react';
import CsvDropzone from './CsvDropzone';
import PdfDropzone from './PdfDropzone';

interface UploadPanelProps {
  dbFile: File | null;
  pdfFiles: File[];
  onDbDrop: (file: File | null) => void;
  onPdfDrop: (files: File[]) => void;
  onDbRemove: () => void;
  onPdfRemove: (index: number) => void;
}

const formatSize = (size: number) => `${(size / 1024).toFixed(1)} KB`;

const UploadPanel: React.FC<UploadPanelProps> = ({
  dbFile,
  pdfFiles,
  onDbDrop,
  onPdfDrop,
  onDbRemove,
  onPdfRemove,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ background: '#fff', borderRadius: '12px', padding: '16px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
        <div style={{ fontWeight: 600, marginBottom: '12px', fontSize: '15px' }}>DB CSV</div>
        <CsvDropzone onDrop={onDbDrop} file={dbFile} />
        {dbFile && (
          <div
            style={{
              marginTop: '12px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: '#f1f5f9',
              padding: '8px 12px',
              borderRadius: '8px',
            }}
          >
            <div>
              <div style={{ fontWeight: 600 }}>{dbFile.name}</div>
              <div style={{ fontSize: '12px', color: '#4b5563' }}>{formatSize(dbFile.size)}</div>
            </div>
            <button
              onClick={onDbRemove}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#1d4ed8',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              削除
            </button>
          </div>
        )}
      </div>
      <div style={{ background: '#fff', borderRadius: '12px', padding: '16px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
        <div style={{ fontWeight: 600, marginBottom: '12px', fontSize: '15px' }}>PDFs</div>
        <PdfDropzone onDrop={onPdfDrop} files={pdfFiles} />
        {pdfFiles.length > 0 && (
          <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {pdfFiles.map((file, index) => (
              <div
                key={`${file.name}-${index}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  background: '#f1f5f9',
                  padding: '8px 12px',
                  borderRadius: '8px',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>{file.name}</div>
                  <div style={{ fontSize: '12px', color: '#4b5563' }}>{formatSize(file.size)}</div>
                </div>
                <button
                  onClick={() => onPdfRemove(index)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#1d4ed8',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  削除
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadPanel;
