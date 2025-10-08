import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

interface Props {
  onDrop: (file: File | null) => void;
  file: File | null;
}

const CsvDropzone: React.FC<Props> = ({ onDrop, file }) => {
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onDrop(acceptedFiles[0]);
      }
    },
    [onDrop]
  );

  const handleRejected = useCallback(() => {
    alert('CSV形式のみアップロード可能です。');
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    onDropRejected: handleRejected,
    multiple: false,
    accept: {
      'text/csv': ['.csv'],
    },
  });

  return (
    <div
      {...getRootProps()}
      style={{
        border: '2px dashed #94a3b8',
        borderRadius: '12px',
        padding: '24px',
        textAlign: 'center',
        background: isDragActive ? '#e0f2fe' : '#f8fafc',
        color: '#1d4ed8',
        cursor: 'pointer',
        fontWeight: 500,
        fontSize: '14px',
      }}
    >
      <input {...getInputProps()} />
      {file ? '別のファイルを選択する' : 'ここにドラッグ、またはクリックしてCSVを選択'}
    </div>
  );
};

export default CsvDropzone;
