/* ============================================================
   ScholarGuard — demo data
   Single source of truth for the judging demo.
   Replace with the backend API response when Role 4 is ready.
   Coordinate contract: every box is normalised 0..1 against the
   rendered page, and carries the flagId it belongs to.
   ============================================================ */

const PAPERS = {
  /* ---------- APP-2026-8891 · Priya Sharma ---------- */
  p8891_income: {
    title: 'INCOME CERTIFICATE', sub: 'District Revenue Office', code: 'CERT-7842',
    rows: [
      ['Name of Applicant', 'Priya Sharma'],
      ["Father's Name", 'Rajesh Sharma'],
      ['Date of Birth', '16/08/2005'],
      ['Annual Family Income', '₹90,000', 'suspicious'],
      ['Date of Issue', '15/03/2024'],
      ['Certificate Number', 'INC-7842-2024', 'linked']
    ],
    boxes: [
      { id: 'b-income', flagId: 'f-tamper', x: .487, y: .424, w: .25, h: .060, label: 'Integrity signals · amount field' },
      { id: 'b-certno', flagId: 'f-dup', x: .487, y: .578, w: .33, h: .060, label: 'Certificate number seen elsewhere' }
    ]
  },
  p8891_category: {
    title: 'CATEGORY CERTIFICATE', sub: 'District Social Welfare Office', code: 'CAT-1188',
    rows: [
      ['Name of Applicant', 'Priya Sharna', 'suspiciousName'],
      ["Father's Name", 'Rajesh Sharma'],
      ['Date of Birth', '16/08/2005'],
      ['Category', 'OBC'],
      ['Certificate Number', 'CAT-1188-2024'],
      ['Date of Issue', '22/06/2024']
    ],
    boxes: [
      { id: 'b-name', flagId: 'f-name', x: .487, y: .195, w: .30, h: .060, label: 'Name differs from 4 other documents' }
    ]
  },
  p8891_marksheet: {
    title: 'SECONDARY MARKSHEET', sub: 'State Examination Board', code: 'MS-5521',
    rows: [
      ['Student Name', 'Priya Sharma'], ["Father's Name", 'Rajesh Sharma'],
      ['Date of Birth', '16/08/2005'], ['Year', '2024'],
      ['Total Marks', '462 / 500'], ['Result', 'PASS']
    ], boxes: []
  },
  p8891_id: {
    title: 'IDENTITY PROOF', sub: 'Government Identity Document', code: 'ID-••••-2917',
    rows: [
      ['Name', 'Priya Sharma'], ['Date of Birth', '16/08/2005'],
      ['Address', 'Jaipur, Rajasthan'], ['Masked ID', '•••• •••• 2917'], ['Status', 'Readable']
    ], boxes: []
  },
  p8891_bank: {
    title: 'BANK ACCOUNT PROOF', sub: 'Scheduled Commercial Bank', code: 'ACC-••••-4421',
    rows: [
      ['Account Holder', 'Priya Sharma'], ['Bank', 'State Bank of India'],
      ['Account', '••••••4421'], ['IFSC', 'SBIN0001234'],
      ['Branch', 'Jaipur Main'], ['Status', 'Verified']
    ], boxes: []
  },

  /* ---------- APP-2026-9014 · Anjali Verma (duplicate counterpart) ---------- */
  p9014_income: {
    title: 'INCOME CERTIFICATE', sub: 'District Revenue Office', code: 'CERT-7842',
    rows: [
      ['Name of Applicant', 'Anjali Verma', 'suspiciousName'],
      ["Father's Name", 'Mahesh Verma', 'suspiciousName'],
      ['Date of Birth', '02/11/2004'],
      ['Annual Family Income', '₹90,000'],
      ['Date of Issue', '15/03/2024'],
      ['Certificate Number', 'INC-7842-2024', 'linked']
    ],
    boxes: [
      { id: 'b-certno2', flagId: 'f-dup2', x: .487, y: .578, w: .33, h: .060, label: 'Same certificate number as APP-2026-8891' }
    ]
  },
  p9014_marksheet: {
    title: 'SECONDARY MARKSHEET', sub: 'State Examination Board', code: 'MS-9902',
    rows: [
      ['Student Name', 'Anjali Verma'], ["Father's Name", 'Mahesh Verma'],
      ['Date of Birth', '02/11/2004'], ['Year', '2023'],
      ['Total Marks', '419 / 500'], ['Result', 'PASS']
    ], boxes: []
  },

  /* ---------- APP-2026-8746 · Rahul Meena (clean) ---------- */
  p8746_income: {
    title: 'INCOME CERTIFICATE', sub: 'District Revenue Office', code: 'CERT-3310',
    rows: [
      ['Name of Applicant', 'Rahul Meena'], ["Father's Name", 'Suresh Meena'],
      ['Date of Birth', '09/04/2005'], ['Annual Family Income', '₹64,000'],
      ['Date of Issue', '11/05/2025'], ['Certificate Number', 'INC-3310-2025']
    ], boxes: []
  },
  p8746_marksheet: {
    title: 'SECONDARY MARKSHEET', sub: 'State Examination Board', code: 'MS-4417',
    rows: [
      ['Student Name', 'Rahul Meena'], ["Father's Name", 'Suresh Meena'],
      ['Date of Birth', '09/04/2005'], ['Year', '2024'],
      ['Total Marks', '431 / 500'], ['Result', 'PASS']
    ], boxes: []
  },

  /* ---------- APP-2026-8802 · Sunil Kumar (unreadable scan) ---------- */
  p8802_income: {
    title: 'INCOME CERTIFICATE', sub: 'District Revenue Office', code: 'CERT-••••',
    degraded: true,
    rows: [
      ['Name of Applicant', 'Sunil Kum▒▒', 'unreadable'],
      ["Father's Name", '▒▒▒▒▒ Kumar', 'unreadable'],
      ['Date of Birth', '2▒/0▒/2005', 'unreadable'],
      ['Annual Family Income', '₹ ▒▒,▒▒▒', 'unreadable'],
      ['Date of Issue', '▒▒/▒▒/2025', 'unreadable'],
      ['Certificate Number', 'INC-▒▒▒▒-2025', 'unreadable']
    ],
    boxes: [
      { id: 'b-blur', flagId: 'f-read', x: .08, y: .19, w: .84, h: .47, label: 'Below readable resolution', kind: 'neutral' }
    ]
  }
};

const APPLICATIONS = [
  {
    id: 'APP-2026-8891', name: 'Priya Sharma', institution: 'Govt. Sr. Sec. School, Jaipur',
    level: 'Institute review · Level 1', band: 'high', status: 'Needs review',
    headline: 'Certificate number also used by another applicant',
    composition: [
      ['Integrity signals', '1 finding'],
      ['Value conflicts', '1 finding'],
      ['Cross-application', '1 finding'],
      ['Field variations', '1 finding']
    ],
    readable: 'All 5 documents read cleanly',
    docs: [
      { key: 'p8891_income', name: 'Income Certificate', meta: 'PDF · 1 page', icon: 'IC', state: 'warning', conf: 98 },
      { key: 'p8891_category', name: 'Category Certificate', meta: 'PDF · 1 page', icon: 'CC', state: 'warning', conf: 96 },
      { key: 'p8891_marksheet', name: 'Marksheet', meta: 'PDF · 2 pages', icon: 'MS', state: 'ok', conf: 99 },
      { key: 'p8891_id', name: 'ID Proof', meta: 'PDF · 1 page', icon: 'ID', state: 'ok', conf: 97 },
      { key: 'p8891_bank', name: 'Bank Proof', meta: 'PDF · 1 page', icon: 'BP', state: 'ok', conf: 99 }
    ],
    flags: [
      { id: 'f-dup', sev: 'HIGH', kind: 'high', docKey: 'p8891_income',
        title: 'Certificate number appears in a second application',
        sub: 'INC-7842-2024 · also submitted under APP-2026-9014 (different applicant)',
        basis: 'Ledger match · exact', action: 'cross' },
      { id: 'f-tamper', sev: 'HIGH', kind: 'high', docKey: 'p8891_income',
        title: 'Income amount region flagged for inspection',
        sub: 'Income Certificate · page 1 · 3 independent integrity signals agree',
        basis: 'Corroborated · 3 of 5 signals', action: 'region' },
      { id: 'f-conflict', sev: 'HIGH', kind: 'high', docKey: 'p8891_income',
        title: 'Declared income does not match certificate',
        sub: 'Application form ₹30,000 · Income Certificate ₹90,000',
        basis: 'Deterministic rule', action: 'evidence' },
      { id: 'f-name', sev: 'MEDIUM', kind: 'medium', docKey: 'p8891_category',
        title: 'Name spelled differently on one document',
        sub: 'Priya Sharma · Priya Sharna · consistent on the other 4 documents',
        basis: '92% similarity · likely reading error', action: 'region' }
    ]
  },
  {
    id: 'APP-2026-9014', name: 'Anjali Verma', institution: 'New Horizon College, Kota',
    level: 'Institute review · Level 1', band: 'high', status: 'Needs review',
    headline: 'Shares an income certificate with APP-2026-8891',
    composition: [['Cross-application', '1 finding'], ['Value conflicts', '0 findings']],
    readable: 'All 4 documents read cleanly',
    docs: [
      { key: 'p9014_income', name: 'Income Certificate', meta: 'PDF · 1 page', icon: 'IC', state: 'warning', conf: 97 },
      { key: 'p9014_marksheet', name: 'Marksheet', meta: 'PDF · 1 page', icon: 'MS', state: 'ok', conf: 98 }
    ],
    flags: [
      { id: 'f-dup2', sev: 'HIGH', kind: 'high', docKey: 'p9014_income',
        title: 'Certificate number appears in a second application',
        sub: 'INC-7842-2024 · also submitted under APP-2026-8891 (different applicant)',
        basis: 'Ledger match · exact', action: 'cross' }
    ]
  },
  {
    id: 'APP-2026-8746', name: 'Rahul Meena', institution: 'Govt. Polytechnic, Alwar',
    level: 'Institute review · Level 1', band: 'clear', status: 'No findings',
    headline: 'All 14 cross-checks agree; nothing needs a reviewer',
    composition: [['Checks run', '14 of 14'], ['Findings', 'None']],
    readable: 'All 5 documents read cleanly',
    docs: [
      { key: 'p8746_income', name: 'Income Certificate', meta: 'PDF · 1 page', icon: 'IC', state: 'ok', conf: 99 },
      { key: 'p8746_marksheet', name: 'Marksheet', meta: 'PDF · 1 page', icon: 'MS', state: 'ok', conf: 99 }
    ],
    flags: [],
    cleared: [
      ['Name', 'Identical across 5 documents'],
      ["Father's name", 'Identical across 4 documents'],
      ['Date of birth', 'Identical across 4 documents'],
      ['Declared income', 'Matches certificate exactly'],
      ['Certificate validity', 'Issued 11/05/2025 · within validity'],
      ['Certificate numbers', 'Not seen in any other application'],
      ['Integrity signals', 'No signal raised on any page'],
      ['Scan quality', 'All pages above readable threshold']
    ]
  },
  {
    id: 'APP-2026-8802', name: 'Sunil Kumar', institution: 'Govt. Sr. Sec. School, Bharatpur',
    level: 'Institute review · Level 1', band: 'unreadable', status: 'Re-upload requested',
    headline: 'Scan too low-resolution to read — not judged',
    composition: [['Readable documents', '4 of 5'], ['Findings withheld', '1 document']],
    readable: '1 document below readable threshold',
    docs: [
      { key: 'p8802_income', name: 'Income Certificate', meta: 'JPEG · 1 page', icon: 'IC', state: 'unread', conf: 34 }
    ],
    flags: [
      { id: 'f-read', sev: 'ACTION', kind: 'neutral', docKey: 'p8802_income',
        title: 'Document could not be read reliably',
        sub: 'Character confidence 34% · below the 70% threshold for any comparison',
        basis: 'No mismatch recorded · re-upload requested', action: 'region' }
    ]
  },
  { id: 'APP-2026-8910', name: 'Meena Kumari', institution: 'Govt. College, Sikar',
    level: 'Institute review · Level 1', band: 'medium', status: 'Needs review',
    headline: 'Date of birth differs by one digit between two documents',
    composition: [['Field variations', '1 finding']], readable: 'All 5 documents read cleanly',
    docs: [], flags: [] },
  { id: 'APP-2026-8955', name: 'Imran Sheikh', institution: 'Model Sr. Sec. School, Ajmer',
    level: 'Institute review · Level 1', band: 'clear', status: 'No findings',
    headline: 'All 14 cross-checks agree; nothing needs a reviewer',
    composition: [['Checks run', '14 of 14']], readable: 'All 5 documents read cleanly',
    docs: [], flags: [] },
  { id: 'APP-2026-9021', name: 'Kavita Yadav', institution: 'Govt. Girls College, Bhilwara',
    level: 'Institute review · Level 1', band: 'medium', status: 'Needs review',
    headline: 'Income certificate expires before the disbursement date',
    composition: [['Single-document rules', '1 finding']], readable: 'All 5 documents read cleanly',
    docs: [], flags: [] },
  { id: 'APP-2026-9077', name: 'Deepak Jangid', institution: 'Govt. Polytechnic, Alwar',
    level: 'Institute review · Level 1', band: 'clear', status: 'No findings',
    headline: 'All 14 cross-checks agree; nothing needs a reviewer',
    composition: [['Checks run', '14 of 14']], readable: 'All 5 documents read cleanly',
    docs: [], flags: [] }
];

/* The cross-application pair that powers the duplicate view. */
const DUPLICATE_CASE = {
  sharedValue: 'INC-7842-2024',
  sharedLabel: 'Income certificate number',
  left: {
    appId: 'APP-2026-8891', name: 'Priya Sharma', institution: 'Govt. Sr. Sec. School, Jaipur',
    reviewer: 'Institute Nodal Officer · Jaipur', submitted: '18 Aug 2026', paper: 'p8891_income'
  },
  right: {
    appId: 'APP-2026-9014', name: 'Anjali Verma', institution: 'New Horizon College, Kota',
    reviewer: 'Institute Nodal Officer · Kota', submitted: '02 Sep 2026', paper: 'p9014_income'
  },
  comparison: [
    ['Certificate number', 'INC-7842-2024', 'INC-7842-2024', 'same'],
    ['Issuing office', 'District Revenue Office', 'District Revenue Office', 'same'],
    ['Date of issue', '15/03/2024', '15/03/2024', 'same'],
    ['Annual family income', '₹90,000', '₹90,000', 'same'],
    ['Applicant name', 'Priya Sharma', 'Anjali Verma', 'diff'],
    ["Father's name", 'Rajesh Sharma', 'Mahesh Verma', 'diff'],
    ['Date of birth', '16/08/2005', '02/11/2004', 'diff'],
    ['Reviewing institute', 'Jaipur', 'Kota', 'diff']
  ]
};
