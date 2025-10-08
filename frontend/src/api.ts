import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

export interface StatusTotals {
  tokens: number;
  hit_hinban: number;
  hit_spec: number;
  fail: number;
}

export interface StatusResponse {
  progress: number;
  totals: StatusTotals;
  pages: number;
}

export interface ResultRow {
  pdf_name: string;
  page: number;
  token: string;
  matched_type: 'hinban' | 'spec';
  matched_hinban: string;
  zaiko?: string | null;
}

export interface FailureRow {
  pdf_name: string;
  page: number;
  token: string;
}

export interface ResultsResponse {
  rows: ResultRow[];
  download_url: string;
}

export interface FailuresResponse {
  rows: FailureRow[];
  download_url: string;
}

export interface UploadResponse {
  task_id: string;
}

export interface RetryResponse {
  candidates: string[];
}

const client = axios.create({
  baseURL: API_BASE,
});

export const uploadFiles = async (dbFile: File, pdfFiles: File[]): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('db_csv', dbFile);
  pdfFiles.forEach((file) => formData.append('pdfs', file));
  const response = await client.post<UploadResponse>('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const fetchStatus = async (taskId: string): Promise<StatusResponse> => {
  const response = await client.get<StatusResponse>(`/api/status/${taskId}`);
  return response.data;
};

export const fetchResults = async (taskId: string): Promise<ResultsResponse> => {
  const response = await client.get<ResultsResponse>(`/api/results/${taskId}`);
  return response.data;
};

export const fetchFailures = async (taskId: string): Promise<FailuresResponse> => {
  const response = await client.get<FailuresResponse>(`/api/failures/${taskId}`);
  return response.data;
};

export const retryToken = async (taskId: string, token: string): Promise<RetryResponse> => {
  const response = await client.post<RetryResponse>('/api/retry', { task_id: taskId, token });
  return response.data;
};

export const downloadUrl = (taskId: string, type: 'results' | 'failures'): string => {
  return `${API_BASE}/api/download/${taskId}?type=${type}`;
};
