import http from 'k6/http';
import {check,sleep} from 'k6';

export const options={
  scenarios:{smoke:{executor:'constant-vus',vus:Number(__ENV.VUS||10),duration:__ENV.DURATION||'30s'}},
  thresholds:{http_req_failed:['rate<0.01'],http_req_duration:['p(95)<750'],checks:['rate>0.99']}
};
const base=__ENV.BASE_URL||'http://localhost:8000';
export default function(){
  const health=http.get(`${base}/api/health`);check(health,{'health is 200':r=>r.status===200,'health is healthy':r=>r.json('status')==='healthy'});
  const analytics=http.get(`${base}/api/public/analytics`);check(analytics,{'analytics is 200':r=>r.status===200,'analytics has totals':r=>typeof r.json('total')==='number'});
  sleep(1);
}
