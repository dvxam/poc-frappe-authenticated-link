import { makeStyles } from '@material-ui/core';
import { vidiLogoDataUri } from './vidiLogo';

const useStyles = makeStyles({
  wrapper: {
    backgroundColor: 'white',
    borderRadius: 6,
    padding: '6px 10px',
    display: 'inline-flex',
  },
  img: {
    height: 32,
    width: 'auto',
    display: 'block',
  },
});

export const LogoFull = () => {
  const classes = useStyles();
  return (
    <span className={classes.wrapper}>
      <img className={classes.img} src={vidiLogoDataUri} alt="Vidi" />
    </span>
  );
};
