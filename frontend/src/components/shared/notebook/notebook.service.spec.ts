import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { firstValueFrom } from 'rxjs';

import { NotebookService } from './notebook.service';
import { AnalysisSession, Thesis } from './cell.models';


function buildSession(): AnalysisSession {
  return {
    id: 'session-1',
    ticker: 'MSFT',
    company_name: 'Microsoft',
    title: 'MSFT Analysis',
    created_at: '2026-03-11T10:00:00Z',
    updated_at: '2026-03-11T10:00:00Z',
    is_public: false,
    cells: [],
    scenarios: [],
  };
}


function buildThesis(overrides: Partial<Thesis> = {}): Thesis {
  return {
    id: 'thesis-1',
    session_id: 'session-1',
    ticker: 'MSFT',
    company_name: 'Microsoft',
    title: 'MSFT Acceptance Thesis',
    summary: 'Saved thesis summary',
    cells_snapshot: [],
    scenarios_snapshot: [],
    dcf_snapshot: {},
    created_at: '2026-03-11T10:00:00Z',
    ...overrides,
  };
}


describe('NotebookService', () => {
  let service: NotebookService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(NotebookService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('loads grouped theses into service state', async () => {
    const thesis = buildThesis();
    const requestPromise = firstValueFrom(service.loadTheses());

    const req = httpMock.expectOne('/bullbeargpt/api/notebook/theses?grouped=true');
    expect(req.request.method).toBe('GET');
    req.flush({
      success: true,
      total: 1,
      grouped: {
        MSFT: {
          '2026-03': [thesis],
        },
      },
    });

    const grouped = await requestPromise;
    expect(grouped['MSFT']['2026-03'][0].title).toBe('MSFT Acceptance Thesis');
    expect(service.groupedTheses()['MSFT']['2026-03'][0].id).toBe('thesis-1');
  });

  it('saveThesis upserts grouped thesis state without duplicates', async () => {
    (service as any)._currentSession.set(buildSession());

    const firstSave = firstValueFrom(service.saveThesis({ title: 'MSFT Acceptance Thesis' }));
    const firstReq = httpMock.expectOne('/bullbeargpt/api/notebook/sessions/session-1/save-thesis');
    expect(firstReq.request.method).toBe('POST');
    firstReq.flush({
      thesis: buildThesis(),
      success: true,
    });
    await firstSave;

    expect(service.groupedTheses()['MSFT']['2026-03'].length).toBe(1);
    expect(service.groupedTheses()['MSFT']['2026-03'][0].summary).toBe('Saved thesis summary');

    const secondSave = firstValueFrom(service.saveThesis({ title: 'MSFT Acceptance Thesis Updated' }));
    const secondReq = httpMock.expectOne('/bullbeargpt/api/notebook/sessions/session-1/save-thesis');
    secondReq.flush({
      thesis: buildThesis({
        title: 'MSFT Acceptance Thesis Updated',
        summary: 'Updated thesis summary',
      }),
      success: true,
    });
    await secondSave;

    expect(service.groupedTheses()['MSFT']['2026-03'].length).toBe(1);
    expect(service.groupedTheses()['MSFT']['2026-03'][0].title).toBe('MSFT Acceptance Thesis Updated');
    expect(service.groupedTheses()['MSFT']['2026-03'][0].summary).toBe('Updated thesis summary');
  });

  it('loadThesis opens a thesis tab for the selected history item', async () => {
    const requestPromise = firstValueFrom(service.loadThesis('thesis-1'));

    const req = httpMock.expectOne('/bullbeargpt/api/notebook/theses/thesis-1');
    expect(req.request.method).toBe('GET');
    req.flush({
      success: true,
      thesis: buildThesis(),
    });

    const thesis = await requestPromise;
    expect(thesis.id).toBe('thesis-1');
    expect(service.currentThesis()?.id).toBe('thesis-1');
    expect(service.tabs().length).toBe(1);
    expect(service.tabs()[0].type).toBe('thesis');
    expect(service.tabs()[0].title).toBe('MSFT Acceptance Thesis');
    expect(service.activeTabId()).toBe('thesis-thesis-1');
  });

  it('switches between session and thesis tabs while preserving the active thesis view state', async () => {
    const session = buildSession();
    const sessionRequest = firstValueFrom(service.loadSession(session.id));

    const sessionReq = httpMock.expectOne('/bullbeargpt/api/notebook/sessions/session-1');
    sessionReq.flush(session);
    await sessionRequest;

    const thesisRequest = firstValueFrom(service.loadThesis('thesis-1'));
    const thesisReq = httpMock.expectOne('/bullbeargpt/api/notebook/theses/thesis-1');
    thesisReq.flush({
      success: true,
      thesis: buildThesis(),
    });
    await thesisRequest;

    expect(service.activeTabId()).toBe('thesis-thesis-1');
    expect(service.currentThesis()?.id).toBe('thesis-1');

    service.switchTab('session-session-1');

    expect(service.activeTabId()).toBe('session-session-1');
    expect(service.currentSession()?.id).toBe('session-1');

    service.switchTab('thesis-thesis-1');

    expect(service.activeTabId()).toBe('thesis-thesis-1');
    expect(service.currentThesis()?.id).toBe('thesis-1');
  });

  it('creates a placeholder cell on cell_start so streamed tool output can render before cell_complete', () => {
    (service as any)._currentSession.set(buildSession());

    (service as any).handleSSEEvent({
      type: 'cell_start',
      cell_id: 'cell-stream-1',
    });

    expect(service.cells().length).toBe(1);
    expect(service.cells()[0].id).toBe('cell-stream-1');
    expect(service.cells()[0].ai_output?.content).toBe('');

    (service as any).handleSSEEvent({
      type: 'stream',
      cell_id: 'cell-stream-1',
      chunk: 'Streaming tool answer',
    });

    expect(service.cells()[0].ai_output?.content).toBe('Streaming tool answer');
  });
});
