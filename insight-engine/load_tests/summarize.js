import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m30s', target: 50 },
    { duration: '20s', target: 0 },
  ],
};

export default function () {
  const res = http.get('http://localhost:8000/v1/analysis/summarize/?video_id=123&q=test');
  check(res, { 'status was 200': (r) => r.status == 200 });
  sleep(1);
}