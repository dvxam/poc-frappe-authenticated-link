import { useCallback, useEffect, useState } from 'react';
import {
  Content,
  ContentHeader,
  Header,
  HeaderLabel,
  InfoCard,
  Page,
  Progress,
  ResponseErrorPanel,
  StatusAborted,
  StatusError,
  StatusOK,
  StatusRunning,
  SupportButton,
  Table,
  TableColumn,
} from '@backstage/core-components';
import {
  alertApiRef,
  discoveryApiRef,
  fetchApiRef,
  useApi,
} from '@backstage/core-plugin-api';
import { Button, Grid, Typography, makeStyles } from '@material-ui/core';

/** A GoPhish campaign as returned by `GET /api/campaigns/`. */
type Campaign = {
  id: number;
  name: string;
  created_date: string;
  status: string;
};

/** Stats block from `GET /api/campaigns/:id/summary`. */
type CampaignStats = {
  total: number;
  sent: number;
  opened: number;
  clicked: number;
  submitted_data: number;
  email_reported: number;
  error: number;
};

type CampaignSummary = {
  id: number;
  name: string;
  status: string;
  stats: CampaignStats;
};

/** A recipient row from `GET /api/campaigns/:id`. */
type CampaignResult = {
  email: string;
  first_name: string;
  last_name: string;
  status: string;
  ip: string;
};

/** A timeline event from `GET /api/campaigns/:id`. */
type TimelineEvent = {
  email: string;
  time: string;
  message: string;
};

type FullCampaign = {
  id: number;
  name: string;
  results: CampaignResult[];
  timeline: TimelineEvent[];
};

/** A recipient who clicked, enriched with the click time from the timeline. */
type Clicker = {
  email: string;
  name: string;
  status: string;
  clicked_at?: string;
  ip?: string;
};

// A recipient "clicked" once their status reaches Clicked Link (or Submitted
// Data, which implies a click). GoPhish `status` only reflects the furthest
// action, so these two cover everyone who clicked.
const CLICK_STATUSES = new Set(['Clicked Link', 'Submitted Data']);

/** Derive the clicker list, pulling the earliest click time from the timeline. */
function extractClickers(campaign: FullCampaign): Clicker[] {
  const clickTimeByEmail = new Map<string, string>();
  for (const ev of campaign.timeline ?? []) {
    if (ev.email && CLICK_STATUSES.has(ev.message)) {
      const prev = clickTimeByEmail.get(ev.email);
      if (!prev || new Date(ev.time) < new Date(prev)) {
        clickTimeByEmail.set(ev.email, ev.time);
      }
    }
  }
  return (campaign.results ?? [])
    .filter(r => CLICK_STATUSES.has(r.status))
    .map(r => ({
      email: r.email,
      name: [r.first_name, r.last_name].filter(Boolean).join(' ') || '—',
      status: r.status,
      clicked_at: clickTimeByEmail.get(r.email),
      ip: r.ip,
    }));
}

const useStyles = makeStyles(theme => ({
  statValue: {
    fontSize: '2.2rem',
    fontWeight: 700,
    lineHeight: 1.1,
  },
  statLabel: {
    color: theme.palette.text.secondary,
    textTransform: 'uppercase',
    fontSize: '0.75rem',
    letterSpacing: 0.5,
  },
}));

/** Render a GoPhish status string as a Backstage status chip. */
function renderStatus(status: string) {
  switch (status) {
    case 'Completed':
      return <StatusOK>{status}</StatusOK>;
    case 'In progress':
      return <StatusRunning>{status}</StatusRunning>;
    case 'Queued':
    case 'Created':
      return <StatusAborted>{status}</StatusAborted>;
    case 'Error':
      return <StatusError>{status}</StatusError>;
    default:
      return <>{status || '—'}</>;
  }
}

/** One stat tile. */
const Stat = ({ label, value }: { label: string; value: number }) => {
  const classes = useStyles();
  return (
    <Grid item xs={6} sm={4} md={3}>
      <Typography className={classes.statValue}>{value ?? 0}</Typography>
      <Typography className={classes.statLabel}>{label}</Typography>
    </Grid>
  );
};

export const GophishPage = () => {
  const discovery = useApi(discoveryApiRef);
  const fetchApi = useApi(fetchApiRef);
  const alertApi = useApi(alertApiRef);

  const [campaigns, setCampaigns] = useState<Campaign[]>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error>();

  const [selected, setSelected] = useState<CampaignSummary>();
  const [clickers, setClickers] = useState<Clicker[]>();
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [sending, setSending] = useState<Set<string>>(new Set());

  // All GoPhish calls go through the Backstage proxy (`/api/proxy/gophish/...`),
  // which injects the API key server-side — the key never reaches the browser.
  const call = useCallback(
    async (path: string) => {
      const base = await discovery.getBaseUrl('proxy');
      const res = await fetchApi.fetch(`${base}/gophish${path}`);
      if (!res.ok) {
        const body = await res.text();
        throw new Error(
          `GoPhish API ${res.status} ${res.statusText}: ${body.slice(0, 200)}`,
        );
      }
      return res.json();
    },
    [discovery, fetchApi],
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    call('/api/campaigns/')
      .then((data: Campaign[]) => {
        if (!active) return;
        setCampaigns(data);
        setError(undefined);
      })
      .catch((e: Error) => active && setError(e))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [call]);

  const onSelect = useCallback(
    (id: number) => {
      setSummaryLoading(true);
      setSelected(undefined);
      setClickers(undefined);
      // Summary gives the aggregate stats; the full campaign gives per-recipient
      // results + timeline, from which we derive who clicked.
      Promise.all([
        call(`/api/campaigns/${id}/summary`),
        call(`/api/campaigns/${id}`),
      ])
        .then(([summary, full]: [CampaignSummary, FullCampaign]) => {
          setSelected(summary);
          setClickers(extractClickers(full));
        })
        .catch((e: Error) => setError(e))
        .finally(() => setSummaryLoading(false));
    },
    [call],
  );

  // Send the LMS training email to a clicker: the backend mints the magic link
  // (as the Frappe service user) and sends the templated email via SMTP.
  const sendTraining = useCallback(
    async (email: string) => {
      setSending(prev => new Set(prev).add(email));
      try {
        const base = await discovery.getBaseUrl('gophish');
        const res = await fetchApi.fetch(`${base}/send-training-email`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        const body = await res.json().catch(() => ({} as any));
        if (!res.ok || body?.ok === false) {
          // Backstage error responses are { error: { name, message } }; our
          // own errors are { error: "<string>" }. Handle both.
          const msg =
            typeof body?.error === 'string'
              ? body.error
              : body?.error?.message ||
                body?.message ||
                `Request failed (${res.status})`;
          throw new Error(body?.detail ? `${msg} — ${body.detail}` : msg);
        }
        alertApi.post({
          message: `Training email sent to ${email}`,
          severity: 'success',
          display: 'transient',
        });
      } catch (e) {
        alertApi.post({
          message: `Failed to send training email to ${email}: ${
            (e as Error).message
          }`,
          severity: 'error',
        });
      } finally {
        setSending(prev => {
          const next = new Set(prev);
          next.delete(email);
          return next;
        });
      }
    },
    [discovery, fetchApi, alertApi],
  );

  const clickerColumns: TableColumn<Clicker>[] = [
    { title: 'Email', field: 'email' },
    { title: 'Name', field: 'name' },
    {
      title: 'Status',
      field: 'status',
      render: row => renderStatus(row.status),
    },
    {
      title: 'Clicked at',
      field: 'clicked_at',
      render: row =>
        row.clicked_at ? new Date(row.clicked_at).toLocaleString() : '—',
    },
    { title: 'IP', field: 'ip', render: row => row.ip || '—' },
    {
      title: 'Training',
      sorting: false,
      render: row => (
        <Button
          variant="contained"
          color="primary"
          size="small"
          disabled={sending.has(row.email)}
          onClick={() => sendTraining(row.email)}
        >
          {sending.has(row.email) ? 'Sending…' : 'Send training email'}
        </Button>
      ),
    },
  ];

  const columns: TableColumn<Campaign>[] = [
    { title: 'ID', field: 'id', width: '80px', type: 'numeric' },
    { title: 'Name', field: 'name' },
    {
      title: 'Status',
      field: 'status',
      render: row => renderStatus(row.status),
    },
    {
      title: 'Created',
      field: 'created_date',
      render: row =>
        row.created_date ? new Date(row.created_date).toLocaleString() : '—',
    },
  ];

  return (
    <Page themeId="tool">
      <Header title="GoPhish" subtitle="Phishing campaign statistics">
        <HeaderLabel label="Source" value="GoPhish API" />
      </Header>
      <Content>
        <ContentHeader title="Campaigns">
          <SupportButton>
            Select a campaign to see its delivery and engagement stats. Data
            comes live from the GoPhish admin API.
          </SupportButton>
        </ContentHeader>

        {error && (
          <div style={{ marginBottom: 16 }}>
            <ResponseErrorPanel error={error} />
          </div>
        )}

        <Table<Campaign>
          title="Campaigns"
          options={{ search: true, paging: true, pageSize: 10, padding: 'dense' }}
          isLoading={loading}
          columns={columns}
          data={campaigns ?? []}
          onRowClick={(_e, row) => row && onSelect(row.id)}
          emptyContent={
            <Typography style={{ padding: 16 }} color="textSecondary">
              No campaigns found. Create one in GoPhish, or check that
              GOPHISH_API_KEY is set.
            </Typography>
          }
        />

        <div style={{ marginTop: 24 }}>
          {summaryLoading && <Progress />}
          {selected && (
            <InfoCard
              title={`Statistics — ${selected.name}`}
              subheader={`Status: ${selected.status}`}
            >
              <Grid container spacing={3}>
                <Stat label="Recipients" value={selected.stats.total} />
                <Stat label="Sent" value={selected.stats.sent} />
                <Stat label="Opened" value={selected.stats.opened} />
                <Stat label="Clicked" value={selected.stats.clicked} />
                <Stat
                  label="Submitted data"
                  value={selected.stats.submitted_data}
                />
                <Stat
                  label="Reported"
                  value={selected.stats.email_reported}
                />
                <Stat label="Errors" value={selected.stats.error} />
              </Grid>
            </InfoCard>
          )}

          {selected && clickers && (
            <div style={{ marginTop: 24 }}>
              <Table<Clicker>
                title={`Users who clicked — ${selected.name} (${clickers.length})`}
                options={{ search: true, paging: true, pageSize: 10, padding: 'dense' }}
                columns={clickerColumns}
                data={clickers}
                emptyContent={
                  <Typography style={{ padding: 16 }} color="textSecondary">
                    No one clicked the link in this campaign yet.
                  </Typography>
                }
              />
            </div>
          )}
        </div>
      </Content>
    </Page>
  );
};
