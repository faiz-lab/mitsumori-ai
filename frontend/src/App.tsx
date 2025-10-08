import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  downloadUrl,
  FailureRow,
  fetchFailures,
  fetchResults,
  fetchStatus,
  ResultRow,
  retryToken,
  StatusTotals,
  uploadFiles,
} from './api';
import UploadPanel from './components/UploadPanel';
import StatsCards from './components/StatsCards';
import ProgressBar from './components/ProgressBar';
import ResultsTable from './components/ResultsTable';
import FailuresTable from './components/FailuresTable';
import RetryDialog from './components/RetryDialog';

const PAGE_SIZE = 10;

type ActiveTab = 'results' | 'failures';

const App: React.FC = () => {
  const [dbFile, setDbFile] = useState<File | null>(null);
  const [pdfFiles, setPdfFiles] = useState<File[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [totals, setTotals] = useState<StatusTotals>({ tokens: 0, hit_hinban: 0, hit_spec: 0, fail: 0 });
  const [progress, setProgress] = useState<number>(0);
  const [results, setResults] = useState<ResultRow[]>([]);
  const [failures, setFailures] = useState<FailureRow[]>([]);
  const [activeTab, setActiveTab] = useState<ActiveTab>('results');
  const [search, setSearch] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [retryTokenValue, setRetryTokenValue] = useState<string>('');
  const [retryCandidates, setRetryCandidates] = useState<string[]>([]);
  const [retryOpen, setRetryOpen] = useState<boolean>(false);
  const [retryLoading, setRetryLoading] = useState<boolean>(false);
  const [retryAttempted, setRetryAttempted] = useState<boolean>(false);

  useEffect(() => {
    let timer: number | undefined;
    if (taskId) {
      const poll = async () => {
        try {
          const status = await fetchStatus(taskId);
          setProgress(status.progress);
          setTotals(status.totals);
          if (status.progress >= 100) {
            setIsProcessing(false);
            const [resultsData, failuresData] = await Promise.all([
              fetchResults(taskId),
              fetchFailures(taskId),
            ]);
            setResults(resultsData.rows);
            setFailures(failuresData.rows);
            window.clearInterval(timer);
          }
        } catch (err: any) {
          window.clearInterval(timer);
          setIsProcessing(false);
          setError(err?.response?.data?.detail ?? '進捗取得中にエラーが発生しました。');
        }
      };
      poll();
      timer = window.setInterval(poll, 1500);
    }
    return () => {
      if (timer) {
        window.clearInterval(timer);
      }
    };
  }, [taskId]);

  const handleStart = useCallback(async () => {
    if (!dbFile || pdfFiles.length === 0) {
      setError('DB CSV と PDF を選択してください。');
      return;
    }
    setError(null);
    setResults([]);
    setFailures([]);
    setProgress(0);
    setTaskId(null);
    setTotals({ tokens: 0, hit_hinban: 0, hit_spec: 0, fail: 0 });
    setIsProcessing(true);
    try {
      const response = await uploadFiles(dbFile, pdfFiles);
      setTaskId(response.task_id);
    } catch (err: any) {
      setIsProcessing(false);
      setError(err?.response?.data?.detail ?? 'アップロードに失敗しました。');
    }
  }, [dbFile, pdfFiles]);

  const handleRetry = useCallback(
    async (token: string) => {
      if (!taskId) return;
      setRetryLoading(true);
      setRetryCandidates([]);
      setRetryAttempted(false);
      try {
        const response = await retryToken(taskId, token);
        setRetryCandidates(response.candidates);
        setRetryAttempted(true);
      } catch (err: any) {
        setRetryCandidates([]);
        setError(err?.response?.data?.detail ?? '再照合に失敗しました。');
        setRetryAttempted(true);
      } finally {
        setRetryLoading(false);
      }
    },
    [taskId]
  );

  const filteredResults = useMemo(() => {
    const keyword = search.trim().toUpperCase();
    return results.filter((row) =>
      keyword ? row.token.toUpperCase().includes(keyword) || row.matched_hinban.toUpperCase().includes(keyword) : true
    );
  }, [results, search]);

  const filteredFailures = useMemo(() => {
    const keyword = search.trim().toUpperCase();
    return failures.filter((row) => (keyword ? row.token.toUpperCase().includes(keyword) : true));
  }, [failures, search]);

  useEffect(() => {
    setPage(1);
  }, [search, activeTab, results.length, failures.length]);

  const paginatedData = useMemo(() => {
    const source = activeTab === 'results' ? filteredResults : filteredFailures;
    const start = (page - 1) * PAGE_SIZE;
    return source.slice(start, start + PAGE_SIZE);
  }, [filteredResults, filteredFailures, page, activeTab]);

  const totalPages = useMemo(() => {
    const source = activeTab === 'results' ? filteredResults : filteredFailures;
    return Math.max(1, Math.ceil(source.length / PAGE_SIZE));
  }, [filteredResults, filteredFailures, activeTab]);

  const onDbDrop = (file: File | null) => {
    setDbFile(file);
  };

  const onPdfDrop = (files: File[]) => {
    setPdfFiles(files);
  };

  const onRetryClick = (token: string) => {
    setRetryTokenValue(token);
    setRetryCandidates([]);
    setRetryAttempted(false);
    setRetryOpen(true);
  };

  const downloadResultsUrl = taskId ? downloadUrl(taskId, 'results') : '#';
  const downloadFailuresUrl = taskId ? downloadUrl(taskId, 'failures') : '#';

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc' }}>
      <header
        style={{
          backgroundColor: '#ffffff',
          padding: '16px 32px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
          fontWeight: 600,
          fontSize: '18px',
        }}
      >
        AI見積システム
      </header>
      <div style={{ display: 'flex', padding: '24px', gap: '24px' }}>
        <div
          style={{
            width: '360px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
          }}
        >
          <UploadPanel
            dbFile={dbFile}
            pdfFiles={pdfFiles}
            onDbDrop={onDbDrop}
            onPdfDrop={onPdfDrop}
            onDbRemove={() => setDbFile(null)}
            onPdfRemove={(index) => setPdfFiles((prev) => prev.filter((_, i) => i !== index))}
          />
          <button
            onClick={handleStart}
            disabled={isProcessing || !dbFile || pdfFiles.length === 0}
            style={{
              backgroundColor: isProcessing || !dbFile || pdfFiles.length === 0 ? '#9ca3af' : '#1d4ed8',
              color: '#fff',
              border: 'none',
              borderRadius: '12px',
              padding: '12px',
              fontSize: '16px',
              cursor: isProcessing || !dbFile || pdfFiles.length === 0 ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.2s ease',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          >
            処理を開始する
          </button>
          <div style={{ background: '#fff', borderRadius: '12px', padding: '16px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
            <div style={{ marginBottom: '8px', fontWeight: 600 }}>進捗状況</div>
            <ProgressBar progress={progress} />
            <div style={{ marginTop: '8px', fontSize: '14px', color: '#4b5563' }}>{progress}% 完了</div>
          </div>
          <StatsCards totals={totals} />
          {error && (
            <div
              style={{
                background: '#fee2e2',
                color: '#b91c1c',
                borderRadius: '12px',
                padding: '12px',
                fontSize: '14px',
              }}
            >
              {error}
            </div>
          )}
        </div>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div
            style={{
              background: '#fff',
              borderRadius: '12px',
              padding: '16px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              minHeight: '600px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  onClick={() => setActiveTab('results')}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '9999px',
                    border: 'none',
                    backgroundColor: activeTab === 'results' ? '#1d4ed8' : '#e2e8f0',
                    color: activeTab === 'results' ? '#fff' : '#111827',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  結果一覧
                </button>
                <button
                  onClick={() => setActiveTab('failures')}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '9999px',
                    border: 'none',
                    backgroundColor: activeTab === 'failures' ? '#1d4ed8' : '#e2e8f0',
                    color: activeTab === 'failures' ? '#fff' : '#111827',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  失敗一覧
                </button>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <a
                  href={downloadResultsUrl}
                  style={{
                    background: '#1d4ed8',
                    color: '#fff',
                    padding: '8px 16px',
                    borderRadius: '12px',
                    textDecoration: 'none',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                  }}
                >
                  結果CSVをダウンロード
                </a>
                <a
                  href={downloadFailuresUrl}
                  style={{
                    background: '#1d4ed8',
                    color: '#fff',
                    padding: '8px 16px',
                    borderRadius: '12px',
                    textDecoration: 'none',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                  }}
                >
                  失敗CSVをダウンロード
                </a>
              </div>
            </div>
            <div>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="キーワードで検索"
                style={{
                  width: '100%',
                  padding: '12px 16px',
                  borderRadius: '12px',
                  border: '1px solid #d1d5db',
                  fontSize: '14px',
                }}
              />
            </div>
            {activeTab === 'results' ? (
              <ResultsTable rows={paginatedData as ResultRow[]} />
            ) : (
              <FailuresTable rows={paginatedData as FailureRow[]} onRetry={onRetryClick} />
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', fontSize: '14px', color: '#4b5563' }}>
              <span>
                ページ {page} / {totalPages}
              </span>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: '1px solid #cbd5f5',
                    background: page === 1 ? '#e5e7eb' : '#fff',
                    cursor: page === 1 ? 'not-allowed' : 'pointer',
                  }}
                >
                  前へ
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: '1px solid #cbd5f5',
                    background: page === totalPages ? '#e5e7eb' : '#fff',
                    cursor: page === totalPages ? 'not-allowed' : 'pointer',
                  }}
                >
                  次へ
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
      <RetryDialog
        open={retryOpen}
        token={retryTokenValue}
        onClose={() => setRetryOpen(false)}
        onSubmit={(value) => {
          setRetryTokenValue(value);
          handleRetry(value);
        }}
        candidates={retryCandidates}
        loading={retryLoading}
        attempted={retryAttempted}
      />
    </div>
  );
};

export default App;
