import React from 'react';

interface Props {
  progress: number;
}

const ProgressBar: React.FC<Props> = ({ progress }) => {
  return (
    <div style={{ width: '100%', background: '#e2e8f0', borderRadius: '9999px', height: '12px' }}>
      <div
        style={{
          height: '100%',
          width: `${progress}%`,
          background: '#1d4ed8',
          borderRadius: '9999px',
          transition: 'width 0.5s ease',
        }}
      />
    </div>
  );
};

export default ProgressBar;
