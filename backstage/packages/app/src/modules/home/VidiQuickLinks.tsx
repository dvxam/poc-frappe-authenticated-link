import {
  Card,
  CardActionArea,
  CardContent,
  Grid,
  Typography,
  makeStyles,
} from '@material-ui/core';
import SchoolIcon from '@material-ui/icons/School';
import SecurityIcon from '@material-ui/icons/Security';
import AssessmentIcon from '@material-ui/icons/Assessment';
import EmailIcon from '@material-ui/icons/Email';
import { Link as RouterLink } from 'react-router-dom';

type LinkItem = {
  title: string;
  description: string;
  to: string;
  external: boolean;
  icon: JSX.Element;
  color: string;
};

// Ports match the defaults in .env (FRAPPE_PORT, GOPHISH_ADMIN_PORT, MAILPIT_UI_PORT).
const ITEMS: LinkItem[] = [
  {
    title: 'Frappe LMS',
    description: 'Training platform — courses & lessons',
    to: 'http://localhost:8000',
    external: true,
    icon: <SchoolIcon />,
    color: '#6bbea2',
  },
  {
    title: 'GoPhish',
    description: 'Phishing campaigns & results',
    to: 'http://localhost:3333',
    external: true,
    icon: <SecurityIcon />,
    color: '#e67e22',
  },
  {
    title: 'Phishing stats',
    description: 'Campaigns, clickers & training email',
    to: '/gophish',
    external: false,
    icon: <AssessmentIcon />,
    color: '#2a337d',
  },
  {
    title: 'Mailpit',
    description: 'Local mail inbox (test only)',
    to: 'http://localhost:8025',
    external: true,
    icon: <EmailIcon />,
    color: '#9b59b6',
  },
];

const useStyles = makeStyles(theme => ({
  root: {
    padding: theme.spacing(1),
  },
  card: {
    height: '100%',
    borderRadius: 12,
    transition: 'transform .15s ease, box-shadow .15s ease',
    '&:hover': {
      transform: 'translateY(-4px)',
      boxShadow: theme.shadows[8],
    },
  },
  actionArea: {
    height: '100%',
  },
  content: {
    display: 'flex',
    alignItems: 'center',
    gap: theme.spacing(2),
  },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: 14,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#fff',
    flexShrink: 0,
    '& svg': { fontSize: 30 },
  },
  title: {
    fontWeight: 700,
    lineHeight: 1.2,
  },
}));

export const VidiQuickLinks = () => {
  const classes = useStyles();
  return (
    <Grid container spacing={3} className={classes.root}>
      {ITEMS.map(item => {
        const linkProps = item.external
          ? {
              component: 'a',
              href: item.to,
              target: '_blank',
              rel: 'noopener noreferrer',
            }
          : { component: RouterLink, to: item.to };
        return (
          <Grid item xs={12} sm={6} md={3} key={item.title}>
            <Card className={classes.card} elevation={2}>
              {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
              <CardActionArea
                className={classes.actionArea}
                {...(linkProps as any)}
              >
                <CardContent className={classes.content}>
                  <span
                    className={classes.avatar}
                    style={{ backgroundColor: item.color }}
                  >
                    {item.icon}
                  </span>
                  <div>
                    <Typography variant="subtitle1" className={classes.title}>
                      {item.title}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                      {item.description}
                    </Typography>
                  </div>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        );
      })}
    </Grid>
  );
};
