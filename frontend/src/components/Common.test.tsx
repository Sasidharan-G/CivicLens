import {render,screen} from '@testing-library/react';
import {MemoryRouter} from 'react-router-dom';
import {describe,expect,it} from 'vitest';
import {ComplaintCard,PageTitle,severityColor,Stat,statusColor} from './Common';
import type {Complaint} from '../types';
const complaint:Complaint={id:'case-1',reference_number:'CIV-2026-000001',title:'Unsafe pothole',description:'Deep road damage near a school',category:'Pothole',severity:'high',status:'in_progress',latitude:13.08,longitude:80.27,locality:'Adyar',support_count:4,created_at:'2026-07-18T00:00:00Z'};
describe('shared civic UI',()=>{
  it('maps severity and status to visual classes',()=>{expect(severityColor('critical')).toContain('red');expect(severityColor('low')).toContain('emerald');expect(statusColor('resolved')).toContain('emerald');expect(statusColor('duplicate')).toContain('slate')});
  it('renders a complaint summary and detail link',()=>{render(<MemoryRouter><ComplaintCard c={complaint}/></MemoryRouter>);expect(screen.getByRole('link',{name:/unsafe pothole/i})).toHaveAttribute('href','/complaints/case-1');expect(screen.getByText('Adyar')).toBeInTheDocument();expect(screen.getByText('4 supporters')).toBeInTheDocument()});
  it('renders dashboard primitives',()=>{render(<><PageTitle eyebrow="Public insights" title="Civic health" desc="Transparent metrics"/><Stat label="SLA compliance" value="92%" icon="check"/></>);expect(screen.getByRole('heading',{name:'Civic health'})).toBeInTheDocument();expect(screen.getByText('92%')).toBeInTheDocument()});
});
