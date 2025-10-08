import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

interface Props {
  onDrop: (files: File[]) => void;
  files: File[];
}

const PdfDropzone: React.FC<Props> = ({ onDrop, files }) => {
  const handleDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        onDrop([...files, ...acceptedFiles]);
      }
    },
    [onDrop, files]
  );

  const handleRejected = useCallback(() => {
    alert('PDF形式のみアップロード可能です。');
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: handleDrop,
    onDropRejected: handleRejected,
    multiple: true,
    accept: {
      'application/pdf': ['.pdf'],
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
      {files.length > 0 ? 'PDFを追加する' : 'ここにドラッグ、またはクリックしてPDFを選択'}
    </div>
  );
};

export default PdfDropzone;
